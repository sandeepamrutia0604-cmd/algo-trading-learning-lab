"""One-time import of real NSE stocks and their historical candles from a MarketDataAdapter
(Angel One, see adapters/angel_one.py) into this app's own Stock/PriceData tables.

Once imported, a real stock behaves exactly like one of the simulated ALPHA/BETA/... stocks
to every other part of the app (chart, trade ticket, strategies, backtests) -- none of that
code changes. The one difference is Stock.source="angel_one": market_service's simulator
(generate_all/advance/reset_market) skips these stocks so it never overwrites real history
with synthetic candles. Re-run the import (scripts/import_real_stocks.py) to refresh prices;
nothing here refreshes automatically.
"""

from datetime import datetime, time

from sqlalchemy.orm import Session

from ..adapters.base import MarketDataAdapter
from ..models import PriceData, Stock

REAL_STOCKS = [
    {"symbol": "RELIANCE", "name": "Reliance Industries"},
    {"symbol": "TCS", "name": "Tata Consultancy Services"},
    {"symbol": "INFY", "name": "Infosys"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank"},
]


def import_real_stock(db: Session, adapter: MarketDataAdapter, symbol: str, name: str) -> Stock:
    candles = adapter.get_historical_candles(symbol)
    if not candles:
        raise ValueError(f"No historical candles returned for {symbol}")

    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if stock is None:
        stock = Stock(
            symbol=symbol,
            name=name,
            source="angel_one",
            starting_price=candles[0].close,
            current_price=candles[-1].close,
        )
        db.add(stock)
        db.flush()
    else:
        stock.name = name
        stock.source = "angel_one"
        stock.starting_price = candles[0].close
        stock.current_price = candles[-1].close
        db.query(PriceData).filter(PriceData.stock_id == stock.id).delete()

    for candle in candles:
        db.add(
            PriceData(
                stock_id=stock.id,
                timestamp=datetime.combine(candle.date, time.min),
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
        )
    return stock


def import_all_real_stocks(
    db: Session, adapter: MarketDataAdapter, stocks: list[dict] = REAL_STOCKS
) -> list[Stock]:
    imported = [import_real_stock(db, adapter, entry["symbol"], entry["name"]) for entry in stocks]
    db.commit()
    return imported
