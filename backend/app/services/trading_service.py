from sqlalchemy.orm import Session

from ..models import Position, Stock, Trade
from ..models.portfolio import Portfolio
from ..engine import cost_math, exit_math
from . import cost_service, risk_service
from .exceptions import (
    InsufficientFundsError,
    InsufficientSharesError,
    InvalidOrderError,
    InvalidQuantityError,
    StockNotFoundError,
)
from .market_service import latest_market_date, recent_closes


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
    db: Session,
    symbol: str,
    quantity: int,
    reason: str = "Manual trade",
    strategy_id: int | None = None,
    stop_pct: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
) -> Trade:
    """`stop_price` / `target_price` set the position's protective exits (see engine/exit_math.py);
    left out, any exits the position already has are kept. They apply to the whole position."""
    if quantity <= 0:
        raise InvalidQuantityError("Quantity must be a positive integer")

    stock = get_stock_by_symbol(db, symbol)
    portfolio = get_portfolio(db)
    costs = cost_service.config(db)
    market_price = stock.current_price
    problem = exit_math.check_levels(stop_price, target_price, market_price)
    if problem:
        raise InvalidOrderError(problem)
    fill = cost_math.fill_price(market_price, "BUY", costs)
    value = fill * quantity
    fees = cost_math.charges(value, costs)
    cost = value + fees

    if cost > portfolio.virtual_cash:
        raise InsufficientFundsError(
            f"Buying {quantity} {stock.symbol} costs ₹{cost:,.2f}"
            + (f" (including ₹{fees:,.2f} of charges)" if fees else "")
            + f", but only ₹{portfolio.virtual_cash:,.2f} cash is available"
        )
    risk_service.check_buy_allowed(db, stock, quantity, market_price)

    # A position's average price is its cost basis per share, buy-side charges included, so a
    # later sale's realized P&L comes out net of everything paid to get in and out.
    unit_cost = fill if not fees else cost / quantity
    position = db.query(Position).filter(Position.stock_id == stock.id).first()
    if position is None:
        position = Position(stock_id=stock.id, quantity=quantity, average_price=unit_cost)
        db.add(position)
    else:
        total_cost = position.quantity * position.average_price + cost
        position.quantity += quantity
        position.average_price = total_cost / position.quantity
    if stop_price is not None:
        position.stop_price = stop_price
    if target_price is not None:
        position.target_price = target_price

    portfolio.virtual_cash -= cost

    trade = Trade(
        stock_id=stock.id,
        side="BUY",
        quantity=quantity,
        price=fill,
        market_price=market_price,
        fees=fees,
        reason=reason,
        strategy_id=strategy_id,
        market_date=latest_market_date(db),
        stop_pct=stop_pct,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def execute_sell(
    db: Session,
    symbol: str,
    quantity: int,
    reason: str = "Manual trade",
    strategy_id: int | None = None,
    market_price: float | None = None,
) -> Trade:
    """`market_price` sells at that quote instead of the stock's current price: a stop-loss or
    take-profit that triggered earlier in the day sells at its own level, not at the close."""
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

    costs = cost_service.config(db)
    if market_price is None:
        market_price = stock.current_price
    fill = cost_math.fill_price(market_price, "SELL", costs)
    proceeds = fill * quantity
    fees = cost_math.charges(proceeds, costs)
    realized = (fill - position.average_price) * quantity - fees

    portfolio.virtual_cash += proceeds - fees
    portfolio.realized_pnl += realized

    position.quantity -= quantity
    if position.quantity == 0:
        db.delete(position)

    trade = Trade(
        stock_id=stock.id,
        side="SELL",
        quantity=quantity,
        price=fill,
        market_price=market_price,
        fees=fees,
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
        if stock.source == "simulated":
            stock.current_price = stock.starting_price
        else:
            # An imported stock's history isn't regenerated by a reset, so its price is the
            # newest candle -- starting_price is its oldest one.
            closes = recent_closes(db, stock.id, 1)
            if closes:
                stock.current_price = closes[-1]

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
