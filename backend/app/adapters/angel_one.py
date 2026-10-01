"""Angel One (SmartAPI) market data adapter: real daily historical candles and LTP quotes
for NSE equities, resolved against the published scrip master.

Angel One is a data source only in this project -- this adapter has no method that places,
modifies or cancels an order, and never will. A "paper order" means a strategy's signal gets
booked against our own virtual portfolio in services/trading_service.py; Angel One's own
order-placement endpoints are simply never called from this codebase. See the Phase 12 note
in the project plan and the README's Security and Safety Principles.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from ..services.exceptions import StockNotFoundError
from .angel_one_auth import BASE_URL, AngelOneAuth, unwrap
from .base import Candle, MarketDataAdapter
from .scrip_master import DEFAULT_CACHE_PATH, build_token_map, load_scrip_master

HISTORICAL_PATH = "/rest/secure/angelbroking/historical/v1/getCandleData"
LTP_PATH = "/order-service/rest/secure/angelbroking/order/v1/getLtpData"

# SmartAPI's published per-second caps (see docs/RateLimit): getCandleData allows 3/sec,
# getLtpData allows 10/sec. A small minimum gap between calls keeps us under both without
# needing a full token-bucket implementation for what is, for now, single-threaded traffic.
CANDLE_MIN_INTERVAL = 0.35
LTP_MIN_INTERVAL = 0.11

CANDLE_CACHE_TTL = timedelta(seconds=60)
DEFAULT_HISTORY_DAYS = 400


class _RateLimiter:
    def __init__(self, min_interval_seconds: float):
        self.min_interval = min_interval_seconds
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


class AngelOneMarketDataAdapter(MarketDataAdapter):
    def __init__(
        self,
        api_key: str,
        client_code: str,
        pin: str,
        totp_secret: str,
        *,
        exchange: str = "NSE",
        scrip_master_cache_path: Path = DEFAULT_CACHE_PATH,
        http: httpx.Client | None = None,
    ):
        self.exchange = exchange
        self.http = http or httpx.Client(base_url=BASE_URL, timeout=15.0)
        self.auth = AngelOneAuth(api_key, client_code, pin, totp_secret, http=self.http)
        self.scrip_master_cache_path = scrip_master_cache_path
        self._token_map: dict[str, str] | None = None
        self._candle_cache: dict[str, tuple[datetime, list[Candle]]] = {}
        self._candle_limiter = _RateLimiter(CANDLE_MIN_INTERVAL)
        self._ltp_limiter = _RateLimiter(LTP_MIN_INTERVAL)

    def _token_for(self, symbol: str) -> str:
        if self._token_map is None:
            master = load_scrip_master(self.http, self.scrip_master_cache_path)
            self._token_map = build_token_map(master)
        try:
            return self._token_map[symbol.upper()]
        except KeyError:
            raise StockNotFoundError(f"Unknown Angel One NSE equity symbol: {symbol}") from None

    def resolve_instrument_token(self, symbol: str) -> str:
        """Public alias for _token_for, for callers (e.g. an admin/debug script) that just
        want the token without fetching candles."""
        return self._token_for(symbol)

    def _fetch_candles(self, symbol: str, token: str, days: int) -> list[Candle]:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        body = {
            "exchange": self.exchange,
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M"),
        }
        self._candle_limiter.wait()
        response = self.http.post(HISTORICAL_PATH, json=body, headers=self.auth.auth_headers())
        rows = unwrap(response, "getCandleData") or []
        return [
            Candle(
                date=datetime.fromisoformat(row[0]).date(),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=int(row[5]),
            )
            for row in rows
        ]

    def get_historical_candles(self, symbol: str, limit: int | None = None) -> list[Candle]:
        token = self._token_for(symbol)
        cache_key = symbol.upper()
        cached = self._candle_cache.get(cache_key)
        if cached and datetime.now() - cached[0] < CANDLE_CACHE_TTL:
            candles = cached[1]
        else:
            candles = self._fetch_candles(symbol, token, DEFAULT_HISTORY_DAYS)
            self._candle_cache[cache_key] = (datetime.now(), candles)
        return candles[-limit:] if limit else candles

    def get_latest_price(self, symbol: str) -> float | None:
        token = self._token_for(symbol)
        body = {"exchange": self.exchange, "tradingsymbol": f"{symbol.upper()}-EQ", "symboltoken": token}
        self._ltp_limiter.wait()
        response = self.http.post(LTP_PATH, json=body, headers=self.auth.auth_headers())
        data = unwrap(response, "getLtpData")
        if not data:
            return None
        row = data[0] if isinstance(data, list) else data
        return float(row["ltp"])
