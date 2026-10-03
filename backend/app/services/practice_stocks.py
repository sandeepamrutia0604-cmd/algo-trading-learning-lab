"""Practice stocks you create yourself: made-up companies whose prices the simulator generates,
exactly like ALPHA/BETA/GAMMA/DELTA. You choose the symbol, name, starting price and how the
price behaves (the same four models as Market settings); history is generated up to where the
market clock is now, and from then on the stock advances, regenerates and resets like the
built-in ones. They are ordinary Stock rows with source "simulated", so charts, trading,
strategies and backtests need no special handling.

The four built-in stocks can't be deleted (startup would put them straight back), and neither
can a stock you've traded or built a strategy on, so nothing in your history ever points at a
stock that no longer exists.
"""

import random

from sqlalchemy.orm import Session

from ..engine.price_models import MODELS, generate_candles
from ..models import MarketConfig, Position, PriceData, Stock, Strategy, Trade
from . import market_service
from .exceptions import InvalidStockError, StockNotFoundError
from .real_stocks import SYMBOL_PATTERN

BUILT_IN_SYMBOLS = frozenset(market_service.DEFAULT_CONFIGS)


def is_removable(stock: Stock) -> bool:
    return stock.source == "simulated" and stock.symbol not in BUILT_IN_SYMBOLS


def create(
    db: Session,
    symbol: str,
    name: str | None,
    starting_price: float,
    model: str,
    volatility: float,
    trend: float,
    *,
    seed: int | None = None,
) -> Stock:
    symbol = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(symbol):
        raise InvalidStockError(
            f"'{symbol}' isn't a valid symbol: use 1 to 10 letters, digits, & or - with no spaces"
        )
    if db.query(Stock).filter(Stock.symbol == symbol).first() is not None:
        raise InvalidStockError(f"{symbol} already exists. Pick a different symbol.")
    if model not in MODELS:
        raise InvalidStockError(f"Unknown price model: {model}")
    if starting_price <= 0:
        raise InvalidStockError("The starting price must be greater than zero")
    if volatility <= 0:
        raise InvalidStockError("Volatility must be greater than zero")

    name = (name or "").strip() or f"{symbol} (practice)"
    stock = Stock(symbol=symbol, name=name, starting_price=starting_price, current_price=starting_price, source="simulated")
    db.add(stock)
    db.flush()
    db.add(MarketConfig(stock_id=stock.id, model=model, volatility=volatility, trend=trend))
    db.flush()

    # History from the simulator's start up to the clock, so the new stock lines up with the
    # others (and with any real stocks being replayed) on the same calendar.
    target = market_service.current_date(db)
    minimum = market_service._sim_end_date(market_service.DEFAULT_HISTORY_DAYS)
    if target is None or target < minimum:
        target = minimum
    days = market_service._count_business_days(market_service.SIM_START_DATE, target)
    try:
        market_service._append_days(db, stock, days, random.Random(seed))
    except ValueError as err:
        db.rollback()
        raise InvalidStockError(str(err)) from err
    db.commit()
    return stock


def delete(db: Session, symbol: str) -> None:
    stock = db.query(Stock).filter(Stock.symbol == symbol.strip().upper()).first()
    if stock is None:
        raise StockNotFoundError(f"Unknown stock symbol: {symbol}")
    if not is_removable(stock):
        raise InvalidStockError(
            f"{stock.symbol} can't be deleted: only practice stocks you created can be."
        )
    if db.query(Position).filter(Position.stock_id == stock.id).first() is not None:
        raise InvalidStockError(f"You still hold {stock.symbol}. Sell it first.")
    if db.query(Trade).filter(Trade.stock_id == stock.id).first() is not None:
        raise InvalidStockError(f"{stock.symbol} has trades in your history. Use Reset (which clears trades) first.")
    if db.query(Strategy).filter(Strategy.stock_id == stock.id).first() is not None:
        raise InvalidStockError(f"A strategy is built on {stock.symbol}. Delete the strategy first.")

    db.query(PriceData).filter(PriceData.stock_id == stock.id).delete(synchronize_session=False)
    db.query(MarketConfig).filter(MarketConfig.stock_id == stock.id).delete(synchronize_session=False)
    db.delete(stock)
    db.commit()
