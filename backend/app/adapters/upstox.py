"""Upstox market data adapter: daily historical candles for NSE equities, read with an Upstox
"Analytics Token" -- a free, read-only token (Developer Apps page -> Analytics tab) that lasts a
year, can only call GET endpoints, and needs no static IP for market data.

Upstox is a data source only in this project: this adapter has no method that places, modifies
or cancels an order, and the token it uses couldn't anyway. See the Phase 12 note in the
project plan and the README's Security and Safety Principles.

How it works (all verified against Upstox's published docs and its real instrument file):
  * Upstox identifies a stock by an *instrument key* such as "NSE_EQ|INE002A01018" (segment +
    ISIN), not by its trading symbol. Upstox publishes a daily file of every NSE instrument;
    the NSE_EQ rows with instrument_type "EQ" map a trading symbol (RELIANCE) to its key.
  * Daily candles come from GET /v3/historical-candle/{key}/days/1/{to_date}/{from_date}
    with "Authorization: Bearer <token>"; a request may span up to a decade, data goes back
    to 2000, and each candle is [timestamp, open, high, low, close, volume, open_interest].
"""

import gzip
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx

from ..services.exceptions import StockNotFoundError
from .base import Candle, MarketDataAdapter
from .rate_limiter import RateLimiter

BASE_URL = "https://api.upstox.com"
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
DEFAULT_CACHE_PATH = Path("data/upstox_nse_instruments.json")
INSTRUMENTS_MAX_AGE = timedelta(hours=24)  # Upstox refreshes the file around 6 AM daily

EQUITY_SEGMENT = "NSE_EQ"
# "EQ" is the normal series. A few stocks trade only in the trade-for-trade "BE" series, so
# that is accepted as a fallback when a symbol has no EQ row.
SERIES_BY_PREFERENCE = ("EQ", "BE")

MAX_DAYS_PER_REQUEST = 3650  # Upstox allows one decade of daily candles per request
DEFAULT_HISTORY_DAYS = 5 * 365
MIN_REQUEST_INTERVAL = 0.1  # the published cap is 50 requests a second; this is far below it
CANDLE_CACHE_TTL = timedelta(seconds=60)
LATEST_PRICE_LOOKBACK_DAYS = 14  # enough to span a long holiday weekend


class UpstoxError(RuntimeError):
    """The Upstox API (or its token) rejected a request. The message never contains the token.
    `auth_failed` marks a rejected token (HTTP 401/403), which will fail every other request too."""

    def __init__(self, message: str, *, auth_failed: bool = False):
        super().__init__(message)
        self.auth_failed = auth_failed


# ---------- instrument file ----------


def load_instruments(
    http: httpx.Client, cache_path: Path = DEFAULT_CACHE_PATH, max_age: timedelta = INSTRUMENTS_MAX_AGE
) -> list[dict]:
    """The NSE cash-market instruments, from the disk cache if it is fresh enough, else
    downloaded. Only the rows this adapter can use are cached (a few thousand, not the ~74,000
    futures, options and commodities in the full file)."""
    if cache_path.exists():
        age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if age < max_age:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    response = http.get(INSTRUMENTS_URL, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    try:
        raw = gzip.decompress(response.content)
    except OSError:  # already decompressed by the transport
        raw = response.content
    rows = [
        {
            "segment": row["segment"],
            "instrument_type": row["instrument_type"],
            "trading_symbol": row["trading_symbol"],
            "instrument_key": row["instrument_key"],
            "name": row.get("name", ""),
        }
        for row in json.loads(raw)
        if row.get("segment") == EQUITY_SEGMENT and row.get("instrument_type") in SERIES_BY_PREFERENCE
    ]

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def build_instrument_map(rows: list[dict], field: str = "instrument_key") -> dict[str, str]:
    """{trading symbol: row[field]} -- the instrument key by default, or e.g. the company
    name -- preferring a symbol's EQ row over its BE row."""
    mapping: dict[str, str] = {}
    for series in reversed(SERIES_BY_PREFERENCE):  # BE first, so EQ overwrites it
        for row in rows:
            if row.get("segment") == EQUITY_SEGMENT and row.get("instrument_type") == series:
                mapping[row["trading_symbol"]] = row.get(field, "")
    return mapping


# ---------- the adapter ----------


class UpstoxMarketDataAdapter(MarketDataAdapter):
    def __init__(
        self,
        token: str,
        *,
        history_days: int = DEFAULT_HISTORY_DAYS,
        instruments_cache_path: Path = DEFAULT_CACHE_PATH,
        http: httpx.Client | None = None,
    ):
        if not token or not token.strip():
            raise UpstoxError(
                "No Upstox token: set UPSTOX_ANALYTICS_TOKEN in your local .env "
                "(Upstox Developer Apps page -> Analytics tab -> Generate Token)."
            )
        self._token = token.strip()
        self.history_days = max(1, min(history_days, MAX_DAYS_PER_REQUEST))
        self.instruments_cache_path = instruments_cache_path
        self.http = http or httpx.Client(base_url=BASE_URL, timeout=30.0)
        self._instrument_map: dict[str, str] | None = None
        self._instrument_names: dict[str, str] = {}
        self._candle_cache: dict[str, tuple[datetime, list[Candle]]] = {}
        self._limiter = RateLimiter(MIN_REQUEST_INTERVAL)

    def _key_for(self, symbol: str) -> str:
        if self._instrument_map is None:
            rows = load_instruments(self.http, self.instruments_cache_path)
            self._instrument_map = build_instrument_map(rows)
            self._instrument_names = build_instrument_map(rows, "name")
        try:
            return self._instrument_map[symbol.strip().upper()]
        except KeyError:
            raise StockNotFoundError(f"Unknown Upstox NSE equity symbol: {symbol}") from None

    def instrument_name(self, symbol: str) -> str | None:
        """The company's name from Upstox's instrument file, tidied from ALL CAPS ("WIPRO LTD"
        becomes "Wipro Ltd"); None for a symbol Upstox doesn't list."""
        self._key_for(symbol)  # loads the instrument file
        name = self._instrument_names.get(symbol.strip().upper())
        return name.title() if name else None

    def resolve_instrument_key(self, symbol: str) -> str:
        """Public alias for _key_for, for callers (a smoke-test script) that just want the key."""
        return self._key_for(symbol)

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        detail = ""
        try:
            body = response.json()
            errors = body.get("errors") or []
            detail = "; ".join(str(e.get("message", "")) for e in errors if isinstance(e, dict)) or str(body.get("message", ""))
        except ValueError:
            detail = response.text[:200]
        message = f"Upstox returned HTTP {response.status_code}" + (f": {detail}" if detail else "")
        if response.status_code in (401, 403):
            message += (
                " -- the token was rejected. It may be wrong, revoked or expired; "
                "generate a new Analytics Token on Upstox's Developer Apps page."
            )
        return message

    def _fetch_candles(self, key: str, days: int) -> list[Candle]:
        to_date = date.today()
        from_date = to_date - timedelta(days=days)
        path = f"/v3/historical-candle/{quote(key, safe='')}/days/1/{to_date:%Y-%m-%d}/{from_date:%Y-%m-%d}"
        self._limiter.wait()
        response = self.http.get(
            path, headers={"Accept": "application/json", "Authorization": f"Bearer {self._token}"}
        )
        if response.status_code != 200:
            raise UpstoxError(self._error_message(response), auth_failed=response.status_code in (401, 403))
        body = response.json()
        if body.get("status") != "success":
            raise UpstoxError(f"Upstox did not return candles: {body.get('message') or body}")

        by_date: dict[date, Candle] = {}
        for row in (body.get("data") or {}).get("candles") or []:
            day = datetime.fromisoformat(row[0]).date()
            by_date[day] = Candle(
                date=day,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=int(row[5]),
            )
        return [by_date[d] for d in sorted(by_date)]  # the API's own order isn't relied on

    def get_historical_candles(self, symbol: str, limit: int | None = None) -> list[Candle]:
        key = self._key_for(symbol)
        cache_key = symbol.strip().upper()
        cached = self._candle_cache.get(cache_key)
        if cached and datetime.now() - cached[0] < CANDLE_CACHE_TTL:
            candles = cached[1]
        else:
            candles = self._fetch_candles(key, self.history_days)
            self._candle_cache[cache_key] = (datetime.now(), candles)
        return candles[-limit:] if limit else candles

    def get_latest_price(self, symbol: str) -> float | None:
        """The most recent daily close. (Upstox also has a live quote endpoint; daily candles
        are all this lab's strategies and charts use, so the last close is what's needed.)"""
        candles = self._fetch_candles(self._key_for(symbol), LATEST_PRICE_LOOKBACK_DAYS)
        return candles[-1].close if candles else None
