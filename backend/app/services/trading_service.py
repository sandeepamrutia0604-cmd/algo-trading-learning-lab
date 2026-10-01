from sqlalchemy.orm import Session

from ..models import Position, Stock, Trade
from ..models.portfolio import Portfolio
from . import risk_service
from .exceptions import (
    InsufficientFundsError,
    InsufficientSharesError,
    InvalidQuantityError,
    StockNotFoundError,
)
from .market_service import latest_market_date


def get_portfolio(db: Session) -> Portfolio:
    portfolio = db.query(Portfolio).first()
    if portfolio is None:
        raise RuntimeError("Portfolio not seeded — call ensure_seed_data() at startup")
    return portfolio


def get_stock_by_symbol(db: Session, symbol: str) -> Stock:
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if stock is None:
        raise StockNotFoundError(f"Unknown stock symbol: {symbol}")
    return stock


def execute_buy(
    db: Session, symbol: str, quantity: int, reason: str = "Manual trade", strategy_id: int | None = None
) -> Trade:
    if quantity <= 0:
        raise InvalidQuantityError("Quantity must be a positive integer")

    stock = get_stock_by_symbol(db, symbol)
    portfolio = get_portfolio(db)
    cost = stock.current_price * quantity

    if cost > portfolio.virtual_cash:
        raise InsufficientFundsError(
            f"Buying {quantity} {stock.symbol} costs ₹{cost:,.2f}, "
            f"but only ₹{portfolio.virtual_cash:,.2f} cash is available"
        )
    risk_service.check_buy_allowed(db, stock, quantity, stock.current_price)

    position = db.query(Position).filter(Position.stock_id == stock.id).first()
    if position is None:
        position = Position(stock_id=stock.id, quantity=quantity, average_price=stock.current_price)
        db.add(position)
    else:
        total_cost = position.quantity * position.average_price + cost
        position.quantity += quantity
        position.average_price = total_cost / position.quantity

    portfolio.virtual_cash -= cost

    trade = Trade(
        stock_id=stock.id,
        side="BUY",
        quantity=quantity,
        price=stock.current_price,
        reason=reason,
        strategy_id=strategy_id,
        market_date=latest_market_date(db),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def execute_sell(
    db: Session, symbol: str, quantity: int, reason: str = "Manual trade", strategy_id: int | None = None
) -> Trade:
    if quantity <= 0:
        raise InvalidQuantityError("Quantity must be a positive integer")

    stock = get_stock_by_symbol(db, symbol)
    portfolio = get_portfolio(db)
    position = db.query(Position).filter(Position.stock_id == stock.id).first()

    if position is None or position.quantity < quantity:
        held = position.quantity if position else 0
        raise InsufficientSharesError(
            f"Cannot sell {quantity} {stock.symbol} — only {held} held"
        )

    proceeds = stock.current_price * quantity
    realized = (stock.current_price - position.average_price) * quantity

    portfolio.virtual_cash += proceeds
    portfolio.realized_pnl += realized

    position.quantity -= quantity
    if position.quantity == 0:
        db.delete(position)

    trade = Trade(
        stock_id=stock.id,
        side="SELL",
        quantity=quantity,
        price=stock.current_price,
        reason=reason,
        strategy_id=strategy_id,
        market_date=latest_market_date(db),
        realized_pnl=realized,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def reset_simulation(db: Session) -> None:
    db.query(Trade).delete()
    db.query(Position).delete()

    portfolio = get_portfolio(db)
    portfolio.virtual_cash = portfolio.starting_capital
    portfolio.realized_pnl = 0.0

    for stock in db.query(Stock).all():
        stock.current_price = stock.starting_price

    db.commit()


def set_starting_capital(db: Session, amount: float) -> Portfolio:
    """Change the paper-trading bankroll and reset the simulation to it -- the old cash/
    trades/positions were all sized against the previous capital, so keeping them around
    under a new baseline would make every P&L and return % figure meaningless."""
    portfolio = get_portfolio(db)
    portfolio.starting_capital = amount
    db.commit()
    reset_simulation(db)
    return portfolio
