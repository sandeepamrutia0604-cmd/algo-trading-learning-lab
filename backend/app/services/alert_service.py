"""Price alerts (the maths is in engine/alert_math.py).

An alert watches one stock for a price above or below a level you chose. It never trades. As the
market advances one day at a time, each active alert is checked against that day's candle; one that
is reached is marked triggered (with the day and price) and reported, and stays in the list until
you delete it or re-arm it.
"""

from sqlalchemy.orm import Session

from ..engine import alert_math
from ..models import PriceAlert
from . import market_service, trading_service
from .exceptions import InvalidOrderError, TradingError

MAX_ALERTS = 200


class AlertNotFoundError(TradingError):
    pass


def any_active(db: Session) -> bool:
    return db.query(PriceAlert).filter(PriceAlert.active.is_(True)).count() > 0


def create(db: Session, symbol: str, kind: str, level: float, note: str | None) -> PriceAlert:
    stock = trading_service.get_stock_by_symbol(db, symbol)
    problem = alert_math.check_level(kind, level, stock.current_price)
    if problem:
        raise InvalidOrderError(problem)
    if db.query(PriceAlert).count() >= MAX_ALERTS:
        raise TradingError(f"You can keep up to {MAX_ALERTS} alerts. Delete some you no longer need first.")
    row = PriceAlert(symbol=stock.symbol, kind=kind, level=level, note=(note or "").strip() or None)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_all(db: Session) -> list[PriceAlert]:
    return db.query(PriceAlert).order_by(PriceAlert.active.desc(), PriceAlert.id.desc()).all()


def get(db: Session, alert_id: int) -> PriceAlert:
    row = db.get(PriceAlert, alert_id)
    if row is None:
        raise AlertNotFoundError(f"Alert {alert_id} doesn't exist (it may have been deleted)")
    return row


def delete(db: Session, alert_id: int) -> None:
    db.delete(get(db, alert_id))
    db.commit()


def delete_all(db: Session) -> None:
    db.query(PriceAlert).delete()
    db.commit()


def rearm(db: Session, alert_id: int) -> PriceAlert:
    """Switch a triggered alert back on. It must still make sense at today's price."""
    row = get(db, alert_id)
    stock = trading_service.get_stock_by_symbol(db, row.symbol)
    problem = alert_math.check_level(row.kind, row.level, stock.current_price)
    if problem:
        raise InvalidOrderError(problem)
    row.active = True
    row.triggered_date = None
    row.triggered_price = None
    db.commit()
    db.refresh(row)
    return row


def run_alerts(db: Session) -> list[str]:
    """Check every active alert against the market day that has just arrived. Returns a line for
    each one that fired. A stock with no candle on that day (a holiday in its own data, or a stock
    deleted since) is skipped."""
    today = market_service.latest_market_date(db)
    events: list[str] = []
    for alert in db.query(PriceAlert).filter(PriceAlert.active.is_(True)).all():
        candles = market_service.get_prices(db, alert.symbol, limit=1)
        if not candles or candles[-1].timestamp.date() != today:
            continue
        candle = candles[-1]
        hit = alert_math.alert_hit(alert.kind, alert.level, candle.open, candle.high, candle.low)
        if hit is None:
            continue
        alert.active = False
        alert.triggered_date = today
        alert.triggered_price = hit.price
        verb = "rose to" if alert.kind == "above" else "fell to"
        line = f"ALERT: {alert.symbol} {verb} ₹{hit.price:,.2f} ({alert.kind} ₹{alert.level:,.2f})"
        if hit.gapped:
            line += ", it opened beyond the level"
        events.append(line)
    db.commit()
    return events
