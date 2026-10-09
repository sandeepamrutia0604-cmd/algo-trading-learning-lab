import math
import random
import zlib
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..engine.price_models import generate_candles
from ..models import MarketConfig, Portfolio, PriceData, Stock
from .exceptions import StockNotFoundError

SIM_START_DATE = date(2025, 1, 1)  # a Wednesday
DEFAULT_HISTORY_DAYS = 60
DESKTOP_HISTORY_DAYS = 760  # about three years: backtests, the optimiser and Monte Carlo need a long history
DEFAULT_SEED = 5
# How many candles of an imported stock are already showing when the market starts, so charts
# and indicators open with the same kind of history a simulated stock does.
WARMUP_DAYS = DEFAULT_HISTORY_DAYS

FALLBACK_CONFIG = ("random_walk", 0.02, 0.0)
DEFAULT_CONFIGS = {
    "ALPHA": ("random_walk", 0.02, 0.0),
    "BETA": ("trending", 0.02, 0.003),
    "GAMMA": ("sideways", 0.015, 0.0),
    "DELTA": ("volatile", 0.015, 0.0),
}


def starting_history_days() -> int:
    """How much simulated history a fresh database (and Reset) starts with. The Windows download opens on
    about three years, so the backtest pages have something to chew on from the first minute."""
    return DESKTOP_HISTORY_DAYS if settings.desktop_mode else DEFAULT_HISTORY_DAYS


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


def _simulated_stocks(db: Session):
    """Stocks whose history this app generates itself -- never the ones imported from a real
    market data provider (see services/real_stocks.py), whose history must stay untouched."""
    return db.query(Stock).filter(Stock.source == "simulated").order_by(Stock.symbol).all()


def _real_stocks(db: Session):
    return db.query(Stock).filter(Stock.source != "simulated").order_by(Stock.symbol).all()


# ---------------------------------------------------------------------------------------------
# The market clock. Portfolio.market_date is the simulated "today", and every stock only shows
# candles up to it. That's what lets an imported stock -- whose full real history is already in
# the database -- replay forward one day at a time like a simulated one: advancing the market
# just moves the clock, revealing the next real candle and generating the next simulated one.
# ---------------------------------------------------------------------------------------------


def current_date(db: Session) -> date | None:
    portfolio = db.query(Portfolio).first()
    if portfolio is not None and portfolio.market_date is not None:
        return portfolio.market_date
    # Clock never started (an older database, or a fresh one): fall back to how far the
    # simulator has run, so existing data keeps working until ensure_clock stores a clock.
    latest = (
        db.query(func.max(PriceData.timestamp))
        .join(Stock, Stock.id == PriceData.stock_id)
        .filter(Stock.source == "simulated")
        .scalar()
    )
    if latest is None:
        latest = db.query(func.max(PriceData.timestamp)).scalar()
    return latest.date() if latest else None


def latest_market_date(db: Session) -> date | None:
    return current_date(db)


def visible_before(db: Session) -> datetime | None:
    """Exclusive upper bound on PriceData.timestamp for candles that have 'happened' by the
    market clock; None when there's no clock yet (everything is visible)."""
    day = current_date(db)
    return datetime.combine(day + timedelta(days=1), time.min) if day else None


def real_data_end(db: Session) -> date | None:
    latest = (
        db.query(func.max(PriceData.timestamp))
        .join(Stock, Stock.id == PriceData.stock_id)
        .filter(Stock.source != "simulated")
        .scalar()
    )
    return latest.date() if latest else None


def at_end_of_real_data(db: Session) -> bool:
    """True once the clock has replayed up to the last real candle, so there's nothing further
    to reveal. (A clock already past all real data isn't 'at the end': nothing is being replayed.)"""
    end = real_data_end(db)
    return end is not None and current_date(db) == end


def _count_business_days(first: date, last: date) -> int:
    count, day = 0, first
    while day <= last:
        if day.weekday() < 5:
            count += 1
        day += timedelta(days=1)
    return count


def _sim_end_date(days: int) -> date:
    day = SIM_START_DATE
    for _ in range(days - 1):
        day = _business_day_after(day)
    return day


def _warm_date(db: Session, stock: Stock) -> date | None:
    """The date of a real stock's WARMUP_DAYS-th candle (or about its midpoint, for a short
    series that would otherwise start with all of its history already played out)."""
    count = db.query(func.count(PriceData.id)).filter(PriceData.stock_id == stock.id).scalar()
    if not count:
        return None
    index = min(WARMUP_DAYS, max(1, count // 2)) - 1
    stamp = (
        db.query(PriceData.timestamp)
        .filter(PriceData.stock_id == stock.id)
        .order_by(PriceData.timestamp)
        .offset(index)
        .limit(1)
        .scalar()
    )
    return stamp.date()


def initial_real_date(db: Session) -> date | None:
    """Where the clock starts when imported stocks exist: late enough that every one of them
    already has its warm-up history showing."""
    dates = [d for d in (_warm_date(db, s) for s in _real_stocks(db)) if d is not None]
    return max(dates) if dates else None


def _extend_sims_to(db: Session, target: date, seed: int | None = None) -> None:
    """Generate simulated candles so each simulated stock's history reaches `target`."""
    for stock in _simulated_stocks(db):
        last = (
            db.query(func.max(PriceData.timestamp)).filter(PriceData.stock_id == stock.id).scalar()
        )
        first_day = SIM_START_DATE if last is None else _business_day_after(last.date())
        missing = _count_business_days(first_day, target)
        if missing > 0:
            _append_days(db, stock, missing, _rng(seed, stock.symbol))


def _sync_real_prices(db: Session) -> None:
    """An imported stock's price is its newest candle that the clock has revealed."""
    for stock in _real_stocks(db):
        closes = recent_closes(db, stock.id, 1)
        if closes:
            stock.current_price = closes[-1]


def _align_clock(db: Session, target: date, seed: int | None = None) -> None:
    _extend_sims_to(db, target, seed)
    portfolio = db.query(Portfolio).first()
    if portfolio is not None:
        portfolio.market_date = target
    _sync_real_prices(db)


def ensure_clock(db: Session) -> None:
    """Start the clock if it hasn't been, and make sure imported stocks have history showing.
    Runs at startup, so a database from before the clock existed picks one up without losing
    anything. Only ever moves the clock forward."""
    candidates = [d for d in (current_date(db), initial_real_date(db)) if d is not None]
    if candidates:
        _align_clock(db, max(candidates))


def ensure_visible(db: Session, stock: Stock) -> None:
    """After importing a stock: if none of its history has happened yet by the clock, move the
    clock up to where it has warm-up history showing. Otherwise just refresh imported prices."""
    db.flush()
    clock = current_date(db)
    first = db.query(func.min(PriceData.timestamp)).filter(PriceData.stock_id == stock.id).scalar()
    if first is not None and (clock is None or first.date() > clock):
        warm = _warm_date(db, stock)
        _align_clock(db, warm if clock is None else max(warm, clock))
    else:
        _sync_real_prices(db)


def generate_all(db: Session, days: int, seed: int | None = None) -> None:
    """Replace every simulated stock's history with `days` fresh candles from its starting
    price and restart the clock at the end of it. Imported stocks are left alone, but if they
    start later than that the clock (and the simulated history) runs on to where they have
    warm-up history showing, so everything shares one calendar."""
    stocks = _simulated_stocks(db)
    stock_ids = [s.id for s in stocks]
    db.query(PriceData).filter(PriceData.stock_id.in_(stock_ids)).delete(synchronize_session=False)
    target = _sim_end_date(days)
    real_start = initial_real_date(db)
    if real_start is not None and real_start > target:
        target = real_start
    _align_clock(db, target, seed)
    db.commit()


def advance(db: Session, days: int) -> None:
    """Move the clock forward `days` business days: imported stocks reveal their next real
    candles, simulated stocks generate theirs. While real data is being replayed, stops at its
    last candle (see at_end_of_real_data)."""
    base = current_date(db)
    start = base if base is not None else SIM_START_DATE - timedelta(days=1)
    end = real_data_end(db)

    target = start
    for _ in range(days):
        following = _business_day_after(target)
        if end is not None and start <= end and following > end:
            break
        target = following
    if target == start:
        return

    _align_clock(db, target)
    db.commit()


def reset_market(db: Session) -> None:
    for stock in _simulated_stocks(db):
        if stock.symbol not in DEFAULT_CONFIGS:
            continue  # a practice stock you created keeps the behaviour you gave it
        config = get_config(db, stock)
        config.model, config.volatility, config.trend = _default_config(stock.symbol)
    generate_all(db, starting_history_days(), seed=DEFAULT_SEED)


def get_prices(db: Session, symbol: str, limit: int | None = None, *, full: bool = False) -> list[PriceData]:
    """A stock's candles up to the market clock, oldest first. `full=True` ignores the clock --
    for backtests, which are historical analysis over the whole series rather than a
    point-in-time view."""
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if stock is None:
        raise StockNotFoundError(f"Unknown stock symbol: {symbol}")
    query = db.query(PriceData).filter(PriceData.stock_id == stock.id)
    bound = None if full else visible_before(db)
    if bound is not None:
        query = query.filter(PriceData.timestamp < bound)
    query = query.order_by(PriceData.timestamp.desc())
    if limit:
        query = query.limit(limit)
    return list(reversed(query.all()))


def recent_closes(db: Session, stock_id: int, n: int = 30) -> list[float]:
    query = db.query(PriceData.close).filter(PriceData.stock_id == stock_id)
    bound = visible_before(db)
    if bound is not None:
        query = query.filter(PriceData.timestamp < bound)
    rows = query.order_by(PriceData.timestamp.desc()).limit(n).all()
    return [r[0] for r in reversed(rows)]
