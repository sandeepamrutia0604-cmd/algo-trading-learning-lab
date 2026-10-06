"""Runs the data-quality checks (engine/data_quality.py) over the candles stored for a stock.

The whole stored history is scanned, including candles the market clock hasn't revealed yet,
because that is what backtests and the optimiser use. Nothing here changes any data."""

from sqlalchemy.orm import Session

from ..adapters.base import Candle
from ..engine import data_quality
from ..models import PriceData, Stock
from .exceptions import StockNotFoundError


def stored_candles(db: Session, stock: Stock) -> list[Candle]:
    rows = db.query(PriceData).filter(PriceData.stock_id == stock.id).order_by(PriceData.timestamp).all()
    return [Candle(r.timestamp.date(), r.open, r.high, r.low, r.close, r.volume) for r in rows]


def _summary(stock: Stock, candles: list[Candle], issues: list[data_quality.Issue]) -> dict:
    found = data_quality.counts(issues)
    return {
        "symbol": stock.symbol,
        "name": stock.name,
        "source": stock.source,
        "candles": len(candles),
        "first_date": candles[0].date if candles else None,
        "last_date": candles[-1].date if candles else None,
        "status": data_quality.status(issues),
        "errors": found["error"],
        "warnings": found["warning"],
        "infos": found["info"],
    }


def summary(db: Session, stock: Stock) -> dict:
    candles = stored_candles(db, stock)
    return _summary(stock, candles, data_quality.scan(candles))


def report(db: Session, symbol: str) -> dict:
    stock = db.query(Stock).filter(Stock.symbol == symbol.strip().upper()).first()
    if stock is None:
        raise StockNotFoundError(f"Unknown stock symbol: {symbol}")
    candles = stored_candles(db, stock)
    issues = data_quality.scan(candles)
    return {
        **_summary(stock, candles, issues),
        "issues": [
            {"kind": i.kind, "severity": i.severity, "message": i.message, "date": i.date, "value": i.value} for i in issues
        ],
    }


def summaries(db: Session) -> list[dict]:
    return [summary(db, stock) for stock in db.query(Stock).order_by(Stock.symbol).all()]
