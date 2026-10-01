"""The market data adapter interface.

Design principle (Phase 11): the strategy engine (strategies/, engine/rule_engine.py), the
backtester (engine/backtest.py) and auto-trading (services/strategy_service.py) should only
ever depend on this interface, never on how candles were actually produced. Today the only
implementation is DummyMarketDataAdapter, serving this app's own simulated random-walk/
trending/volatile/sideways history. A real-market implementation (Angel One/SmartAPI, see
angel_one.py) plugs in later without any of those consumers changing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Candle:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataAdapter(ABC):
    @abstractmethod
    def get_historical_candles(self, symbol: str, limit: int | None = None) -> list[Candle]:
        """OHLCV candles for `symbol`, oldest first. `limit` returns at most the most recent
        `limit` candles. Raises StockNotFoundError for an unknown symbol."""

    @abstractmethod
    def get_latest_price(self, symbol: str) -> float | None:
        """The most recent close for `symbol`, or None if there's no history yet."""
