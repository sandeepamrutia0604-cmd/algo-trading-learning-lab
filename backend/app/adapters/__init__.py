from sqlalchemy.orm import Session

from ..config import settings
from .angel_one import AngelOneMarketDataAdapter
from .base import Candle, MarketDataAdapter
from .dummy import DummyMarketDataAdapter

__all__ = ["Candle", "MarketDataAdapter", "DummyMarketDataAdapter", "AngelOneMarketDataAdapter", "get_market_data_adapter"]


def get_market_data_adapter(db: Session) -> MarketDataAdapter:
    """The adapter the strategy engine/backtester/auto-trader should use for historical
    candles, chosen by MARKET_DATA_PROVIDER (.env). Defaults to the dummy simulator; switching
    to "angel_one" selects that adapter's *shape* today -- its methods still raise
    NotImplementedError until Phase 12 wires up real SmartAPI credentials."""
    if settings.market_data_provider == "angel_one":
        return AngelOneMarketDataAdapter(settings.angel_one_api_key, settings.angel_one_client_code)
    return DummyMarketDataAdapter(db)
