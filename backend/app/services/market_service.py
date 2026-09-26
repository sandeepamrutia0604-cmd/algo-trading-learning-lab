import math
import random
import zlib
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from ..engine.price_models import generate_candles
from ..models import MarketConfig, PriceData, Stock
from .exceptions import StockNotFoundError

SIM_START_DATE = date(2025, 1, 1)  # a Wednesday
DEFAULT_HISTORY_DAYS = 60
DEFAULT_SEED = 5

FALLBACK_CONFIG = ("random_walk", 0.02, 0.0)
DEFAULT_CONFIGS = {
    "ALPHA": ("random_walk", 0.02, 0.0),
    "BETA": ("trending", 0.02, 0.003),
    "GAMMA": ("sideways", 0.015, 0.0),
    "DELTA": ("volatile", 0.015, 0.0),
}


def _default_config(symbol: str) -> tuple[str, float, float]:
    return DEFAULT_CONFIGS.get(symbol, FALLBACK_CONFIG)


def _business_day_after(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _rng(seed: int | None, symbol: str) -> random.Random:
    if seed is None:
        return random.Random()
    return random.Random(seed + zlib.crc32(symbol.encode()))


def get_config(db: Session, stock: Stock) -> MarketConfig:
    config = db.query(MarketConfig).filter(MarketConfig.stock_id == stock.id).first()
    if config is None:
        model, volatility, trend = _default_config(stock.symbol)
        config = MarketConfig(stock_id=stock.id, model=model, volatility=volatility, trend=trend)
        db.add(config)
        db.flush()
    return config


def update_config(db: Session, symbol: str, model: str, volatility: float, trend: float) -> MarketConfig:
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if stock is None:
        raise StockNotFoundError(f"Unknown stock symbol: {symbol}")
    config = get_config(db, stock)
    config.model = model
    config.volatility = volatility
    config.trend = trend
    db.commit()
    return config


def _append_days(db: Session, stock: Stock, n: int, rng: random.Random) -> None:
    config = get_config(db, stock)
    last = (
        db.query(PriceData)
        .filter(PriceData.stock_id == stock.id)
        .order_by(PriceData.timestamp.desc())
        .limit(2)
        .all()
    )

    if not last:
        start_price, day, prev_return, flat_first = stock.starting_price, SIM_START_DATE, 0.0, True
    else:
        start_price = last[0].close
        day = _business_day_after(last[0].timestamp.date())
        prev_return = math.log(last[0].close / last[1].close) if len(last) == 2 else 0.0
        flat_first = False

    candles = generate_candles(
        config.model,
        n,
        start_price,
        config.volatility,
        config.trend,
        rng,
        base_price=stock.starting_price,
        prev_return=prev_return,
        flat_first_open=flat_first,
    )
    for candle in candles:
        db.add(
            PriceData(
                stock_id=stock.id,
                timestamp=datetime.combine(day, time.min),
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
        )
        day = _business_day_after(day)

    stock.current_price = candles[-1].close


def latest_market_date(db: Session) -> date | None:
    latest = db.query(PriceData.timestamp).order_by(PriceData.timestamp.desc()).first()
    return latest[0].date() if latest else None


def generate_all(db: Session, days: int, seed: int | None = None) -> None:
    """Replace every stock's history with `days` fresh candles from its starting price."""
    db.query(PriceData).delete()
    for stock in db.query(Stock).order_by(Stock.symbol).all():
        _append_days(db, stock, days, _rng(seed, stock.symbol))
    db.commit()


def advance(db: Session, days: int) -> None:
    for stock in db.query(Stock).order_by(Stock.symbol).all():
        _append_days(db, stock, days, _rng(None, stock.symbol))
    db.commit()


def reset_market(db: Session) -> None:
    for stock in db.query(Stock).all():
        config = get_config(db, stock)
        config.model, config.volatility, config.trend = _default_config(stock.symbol)
    generate_all(db, DEFAULT_HISTORY_DAYS, seed=DEFAULT_SEED)


def get_prices(db: Session, symbol: str, limit: int | None = None) -> list[PriceData]:
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if stock is None:
        raise StockNotFoundError(f"Unknown stock symbol: {symbol}")
    query = db.query(PriceData).filter(PriceData.stock_id == stock.id).order_by(PriceData.timestamp.desc())
    if limit:
        query = query.limit(limit)
    return list(reversed(query.all()))
