"""Import real NSE stocks and their historical candles -- from a MarketDataAdapter (Angel One
or Upstox, see adapters/angel_one.py and adapters/upstox.py) or from a CSV file (adapters/csv_candles.py) -- into this app's own
Stock/PriceData tables.

Once imported, a real stock behaves exactly like one of the simulated ALPHA/BETA/... stocks
to every other part of the app (chart, trade ticket, strategies, backtests) -- none of that
code changes. The one difference is Stock.source ("angel_one", "upstox" or "csv", never "simulated"):
market_service's simulator skips these stocks so it never overwrites real history with
synthetic candles, and instead the market clock replays their real candles one day at a time
(only candles up to the clock are visible). Nothing here refreshes automatically; re-run
scripts/import_real_stocks.py or scripts/import_csv.py to bring the data up to date.
"""

import re
from datetime import datetime, time

from sqlalchemy.orm import Session

from ..adapters.base import Candle, MarketDataAdapter
from ..models import PriceData, Stock
from . import market_service

SYMBOL_PATTERN = re.compile(r"^[A-Z0-9&-]{1,10}$")

REAL_STOCKS = [
    {"symbol": "RELIANCE", "name": "Reliance Industries"},
    {"symbol": "TCS", "name": "Tata Consultancy Services"},
    {"symbol": "INFY", "name": "Infosys"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank"},
]


def import_candles(
    db: Session, symbol: str, name: str | None, candles: list[Candle], *, source: str, replace: bool
) -> Stock:
    """Write `candles` (oldest first) for `symbol`, creating the stock if needed.

    replace=True discards the stock's existing history first; replace=False merges by date, so
    a short file adds its days and corrects overlapping ones without touching the rest. Either
    way the stock's starting/current price are re-derived from its first and last candle.
    Doesn't commit.
    """
    symbol = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(symbol):
        raise ValueError(
            f"'{symbol}' isn't a valid symbol: use 1 to 10 letters, digits, & or - with no spaces "
            "(for example NIFTY500, M&M or BAJAJ-AUTO)."
        )
    if not candles:
        raise ValueError(f"No candles to import for {symbol}")

    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if stock is not None and stock.source == "simulated":
        raise ValueError(
            f"{symbol} is one of the simulated stocks; importing over it would replace its generated "
            "history. Use a different symbol."
        )

    if stock is None:
        stock = Stock(symbol=symbol, name=name or symbol, source=source, starting_price=0.0, current_price=0.0)
        db.add(stock)
        db.flush()
        existing: dict[datetime, PriceData] = {}
    else:
        if name:
            stock.name = name
        if replace:
            stock.source = source
            db.query(PriceData).filter(PriceData.stock_id == stock.id).delete()
            existing = {}
        else:
            existing = {row.timestamp: row for row in db.query(PriceData).filter(PriceData.stock_id == stock.id)}

    for candle in candles:
        timestamp = datetime.combine(candle.date, time.min)
        row = existing.get(timestamp)
        if row is None:
            row = PriceData(stock_id=stock.id, timestamp=timestamp)
            db.add(row)
        row.open, row.high, row.low, row.close, row.volume = (
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
        )
    db.flush()

    stock.starting_price = (
        db.query(PriceData).filter(PriceData.stock_id == stock.id).order_by(PriceData.timestamp).first().close
    )
    # The price is the newest candle the market clock has reached, not the newest imported one.
    market_service.ensure_visible(db, stock)
    return stock


def import_real_stock(
    db: Session, adapter: MarketDataAdapter, symbol: str, name: str, *, source: str = "angel_one", replace: bool = True
) -> Stock:
    """Fetch a stock's candles from `adapter` and store them. `source` labels where they came
    from ("angel_one", "upstox"); replace=False merges into existing history by date instead of
    discarding it, so a provider that returns less history never shrinks what's already there."""
    candles = adapter.get_historical_candles(symbol)
    return import_candles(db, symbol, name, candles, source=source, replace=replace)


def import_all_real_stocks(
    db: Session,
    adapter: MarketDataAdapter,
    stocks: list[dict] = REAL_STOCKS,
    *,
    source: str = "angel_one",
    replace: bool = True,
) -> list[Stock]:
    imported = [
        import_real_stock(db, adapter, entry["symbol"], entry["name"], source=source, replace=replace) for entry in stocks
    ]
    db.commit()
    return imported
