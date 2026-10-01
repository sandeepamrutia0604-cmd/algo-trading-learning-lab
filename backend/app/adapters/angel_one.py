"""Angel One (SmartAPI) market data adapter -- designed now per the plan, implemented in
Phase 12 (Paper Trading). Nothing in this file makes a network call yet; it exists so the
shape (constructor, methods, symbol-to-token mapping) is right before real credentials and
the SmartAPI client are wired in.

What Phase 12 will need to fill in here:
  - Historical candle API: SmartAPI's getCandleData, used by get_historical_candles() to
    backfill OHLC for backtesting (Phase 6) once a real symbol is added alongside the dummy
    ones.
  - Instrument master (scrip master): Angel One publishes a JSON list of every tradable
    symbol and its instrument token at a fixed URL. load_scrip_master() would download and
    cache it, then resolve_instrument_token() maps our Stock.symbol (e.g. "RELIANCE") to the
    token SmartAPI's APIs expect -- its endpoints take tokens, not trading symbols.
  - WebSocket feed: live LTP ticks, not needed until Phase 12's live-price display; no stub
    here yet.
  - Rate limits: SmartAPI enforces per-second/per-day caps, so a real implementation should
    cache/throttle candle responses rather than call out on every UI refresh -- this class is
    the natural place for that cache, not its callers.
"""

from .base import Candle, MarketDataAdapter

NOT_YET = "Angel One integration arrives in Phase 12 (Paper Trading) -- this adapter's shape is designed, not wired up yet"


def load_scrip_master() -> dict[str, str]:
    """Would download Angel One's published instrument list and return {trading_symbol: token}
    for NSE equities, cached to disk/DB rather than refetched on every lookup."""
    raise NotImplementedError(NOT_YET)


class AngelOneMarketDataAdapter(MarketDataAdapter):
    def __init__(self, api_key: str, client_code: str, instrument_token_map: dict[str, str] | None = None):
        self.api_key = api_key
        self.client_code = client_code
        self.instrument_token_map = instrument_token_map or {}

    def resolve_instrument_token(self, symbol: str) -> str:
        try:
            return self.instrument_token_map[symbol.upper()]
        except KeyError:
            raise NotImplementedError(NOT_YET) from None

    def get_historical_candles(self, symbol: str, limit: int | None = None) -> list[Candle]:
        raise NotImplementedError(NOT_YET)

    def get_latest_price(self, symbol: str) -> float | None:
        raise NotImplementedError(NOT_YET)
