from sqlalchemy.orm import Session

from ..config import settings
from .angel_one import AngelOneMarketDataAdapter
from .base import Candle, MarketDataAdapter
from .dummy import DummyMarketDataAdapter

__all__ = ["Candle", "MarketDataAdapter", "DummyMarketDataAdapter", "AngelOneMarketDataAdapter", "get_market_data_adapter"]


_angel_one_adapter: AngelOneMarketDataAdapter | None = None


def _get_angel_one_adapter() -> AngelOneMarketDataAdapter:
    # A real login session (and its candle cache) is worth reusing across requests, unlike
    # DummyMarketDataAdapter which is cheap to build fresh every time -- constructing a new
    # AngelOneMarketDataAdapter per request would force a fresh login on every call and blow
    # through the 1-request/second login rate limit.
    global _angel_one_adapter
    if _angel_one_adapter is None:
        _angel_one_adapter = AngelOneMarketDataAdapter(
            settings.angel_one_api_key,
            settings.angel_one_client_code,
            settings.angel_one_pin,
            settings.angel_one_totp_secret,
        )
    return _angel_one_adapter


def get_market_data_adapter(db: Session) -> MarketDataAdapter:
    """The adapter the strategy engine/backtester/auto-trader should use for historical
    candles, chosen by MARKET_DATA_PROVIDER (.env). Defaults to the dummy simulator;
    "angel_one" logs into the real SmartAPI account configured in .env."""
    if settings.market_data_provider == "angel_one":
        return _get_angel_one_adapter()
    return DummyMarketDataAdapter(db)
