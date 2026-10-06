"""Stop-loss and take-profit exits on open positions (the maths is in engine/exit_math.py).

A position can carry a stop price and a target price. They are set on a BUY or edited later, and
apply to the whole position. They are checked as the market advances, one day at a time, against
that day's candle; a hit sells the whole position through the ordinary sell path, so slippage,
brokerage and taxes apply exactly as they do to any other sale.
"""

from sqlalchemy.orm import Session

from ..engine import exit_math
from ..models import Position
from . import market_service, trading_service
from .exceptions import InsufficientSharesError, InvalidOrderError


def any_levels(db: Session) -> bool:
    return db.query(Position).filter((Position.stop_price.isnot(None)) | (Position.target_price.isnot(None))).count() > 0


def set_levels(db: Session, symbol: str, stop_price: float | None, target_price: float | None) -> Position:
    """Replace a held position's stop and target (None clears that level)."""
    stock = trading_service.get_stock_by_symbol(db, symbol)
    position = db.query(Position).filter(Position.stock_id == stock.id).first()
    if position is None:
        raise InsufficientSharesError(f"You don't hold any {stock.symbol}, so there is no position to protect.")
    problem = exit_math.check_levels(stop_price, target_price, stock.current_price)
    if problem:
        raise InvalidOrderError(problem)
    position.stop_price = stop_price
    position.target_price = target_price
    db.commit()
    db.refresh(position)
    return position


def _reason(fill: exit_math.ExitFill) -> str:
    label = "Stop-loss" if fill.kind == "stop" else "Take-profit"
    if fill.gapped:
        return f"{label} at ₹{fill.level:,.2f} (the day opened beyond it, so it filled at the open, ₹{fill.price:,.2f})"
    return f"{label} at ₹{fill.level:,.2f}"


def run_exits(db: Session) -> list[str]:
    """Check every position's stop and target against the market day that has just arrived, and
    sell the ones that triggered. Returns a line describing each sale. A stock with no candle on
    that day (a holiday in its own data) is skipped."""
    today = market_service.latest_market_date(db)
    events: list[str] = []
    positions = db.query(Position).filter((Position.stop_price.isnot(None)) | (Position.target_price.isnot(None))).all()
    for position in positions:
        symbol = position.stock.symbol
        candles = market_service.get_prices(db, symbol, limit=1)
        if not candles or candles[-1].timestamp.date() != today:
            continue
        candle = candles[-1]
        fill = exit_math.exit_fill(candle.open, candle.high, candle.low, position.stop_price, position.target_price)
        if fill is None:
            continue
        trade = trading_service.execute_sell(
            db, symbol, position.quantity, reason=_reason(fill), market_price=fill.price
        )
        label = "STOP-LOSS" if fill.kind == "stop" else "TAKE-PROFIT"
        events.append(f"{label}: sold {trade.quantity} {symbol} @ ₹{trade.price:,.2f}")
    return events
