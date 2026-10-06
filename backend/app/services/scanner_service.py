"""Runs one strategy across every stock and reports which are signalling today (see engine/scanner.py).

Each stock is read only up to the market clock, exactly as the chart and the auto-trader see it, so
a scan never peeks at candles that haven't "happened" yet. Nothing here changes any stored data."""

from sqlalchemy.orm import Session

from ..engine import scanner
from ..models import Position, Stock
from ..strategies.base import SignalEvent, StrategyDef
from . import market_service


def _signal_out(event: SignalEvent | None, dates: list, candle_count: int) -> dict | None:
    if event is None:
        return None
    return {
        "side": event.side,
        "date": dates[event.index],
        "days_ago": candle_count - 1 - event.index,
        "headline": event.headline,
        "checks": list(event.checks),
    }


def scan(db: Session, defn: StrategyDef, params: dict) -> list[dict]:
    """One row per stock, best first (today's BUYs, then SELLs, then most recent signals)."""
    held = {p.stock_id: p.quantity for p in db.query(Position).all()}
    rows: list[tuple[tuple[int, int], str, dict]] = []
    for stock in db.query(Stock).order_by(Stock.symbol).all():
        candles = market_service.get_prices(db, stock.symbol)
        dates = [c.timestamp.date() for c in candles]
        closes = [c.close for c in candles]
        events = defn.generate(closes, params) if len(closes) >= 2 else []
        reading = scanner.read(events, len(closes))
        change = (closes[-1] / closes[-2] - 1) * 100 if len(closes) >= 2 and closes[-2] > 0 else None
        rows.append(
            (
                scanner.rank(reading),
                stock.symbol,
                {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "source": stock.source,
                    "candles": len(closes),
                    "price": stock.current_price,
                    "change_pct": change,
                    "held": held.get(stock.id, 0),
                    "state": reading.state,
                    "signal_today": _signal_out(reading.signal_today, dates, len(closes)),
                    "last_signal": _signal_out(reading.last_signal, dates, len(closes)),
                },
            )
        )
    rows.sort(key=lambda r: (r[0], r[1]))
    return [row for _, _, row in rows]
