from sqlalchemy.orm import Session

from ..models import Position, PriceData, Trade
from .market_service import recent_closes, visible_before
from .trading_service import get_portfolio


def _day_pnl(db: Session, position: Position) -> float:
    closes = recent_closes(db, position.stock_id, 2)
    if len(closes) < 2:
        return 0.0
    return position.quantity * (position.stock.current_price - closes[-2])


def get_portfolio_summary(db: Session) -> dict:
    portfolio = get_portfolio(db)
    positions = db.query(Position).all()

    invested = sum(p.quantity * p.average_price for p in positions)
    market_value = sum(p.quantity * p.stock.current_price for p in positions)
    unrealized_pnl = market_value - invested
    portfolio_value = portfolio.virtual_cash + market_value
    total_pnl = portfolio_value - portfolio.starting_capital

    return {
        "cash": portfolio.virtual_cash,
        "invested": invested,
        "market_value": market_value,
        "portfolio_value": portfolio_value,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": portfolio.realized_pnl,
        "day_pnl": sum(_day_pnl(db, p) for p in positions),
        "total_pnl": total_pnl,
        "return_pct": (total_pnl / portfolio.starting_capital) * 100,
        "starting_capital": portfolio.starting_capital,
    }


def get_positions_with_pnl(db: Session) -> list[dict]:
    positions = db.query(Position).all()
    result = []
    for p in positions:
        market_value = p.quantity * p.stock.current_price
        cost_basis = p.quantity * p.average_price
        result.append(
            {
                "symbol": p.stock.symbol,
                "name": p.stock.name,
                "quantity": p.quantity,
                "average_price": p.average_price,
                "current_price": p.stock.current_price,
                "market_value": market_value,
                "unrealized_pnl": market_value - cost_basis,
                "day_pnl": _day_pnl(db, p),
                "stop_price": p.stop_price,
                "target_price": p.target_price,
            }
        )
    return result


def get_equity_curve(db: Session) -> list[dict]:
    """Portfolio value per market day, replaying dated trades over the price history."""
    starting_capital = get_portfolio(db).starting_capital
    closes_by_date: dict = {}
    price_query = db.query(PriceData.stock_id, PriceData.timestamp, PriceData.close)
    bound = visible_before(db)
    if bound is not None:
        price_query = price_query.filter(PriceData.timestamp < bound)
    for stock_id, timestamp, close in price_query.order_by(PriceData.timestamp).all():
        closes_by_date.setdefault(timestamp.date(), {})[stock_id] = close

    trades = (
        db.query(Trade)
        .filter(Trade.market_date.isnot(None))
        .order_by(Trade.market_date, Trade.id)
        .all()
    )

    cash = starting_capital
    holdings: dict[int, int] = {}
    last_close: dict[int, float] = {}
    next_trade = 0
    curve = []

    for day in sorted(closes_by_date):
        last_close.update(closes_by_date[day])
        while next_trade < len(trades) and trades[next_trade].market_date <= day:
            trade = trades[next_trade]
            amount = trade.quantity * trade.price
            fees = trade.fees or 0.0
            if trade.side == "BUY":
                cash -= amount + fees
                holdings[trade.stock_id] = holdings.get(trade.stock_id, 0) + trade.quantity
            else:
                cash += amount - fees
                holdings[trade.stock_id] = holdings.get(trade.stock_id, 0) - trade.quantity
            next_trade += 1
        value = cash + sum(qty * last_close.get(sid, 0.0) for sid, qty in holdings.items())
        curve.append({"date": day, "value": round(value, 2)})

    return curve
