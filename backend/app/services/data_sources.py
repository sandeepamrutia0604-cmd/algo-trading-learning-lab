"""The market data sources a user can import stocks from (Upstox, Angel One), shared by the
Import data tab (api/data_sources.py) and scripts/import_real_stocks.py so both behave the same.

Credentials only ever live in the local .env and are only ever read here, on the server: they
are never returned by the API or typed into the web page. They're re-read from .env on every
call (current_settings), so adding a token takes effect without restarting the app.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..adapters.angel_one import AngelOneMarketDataAdapter
from ..adapters.angel_one_auth import AngelOneAuthError
from ..adapters.base import MarketDataAdapter
from ..adapters.upstox import MAX_DAYS_PER_REQUEST, UpstoxError, UpstoxMarketDataAdapter
from ..config import Settings
from ..models import PriceData, Stock
from . import data_quality_service
from .exceptions import StockNotFoundError
from .real_stocks import REAL_STOCKS, import_real_stock

MAX_YEARS = MAX_DAYS_PER_REQUEST // 365
DEFAULT_YEARS = 5
MAX_SYMBOLS = 25

# source -> display label, the .env names it needs (and the Settings field behind each), and a note
SOURCES = {
    "upstox": {
        "label": "Upstox",
        "needs": {"UPSTOX_ANALYTICS_TOKEN": "upstox_analytics_token"},
        "note": f"Read-only Analytics Token, no static IP needed. Up to {MAX_YEARS} years of daily history (default {DEFAULT_YEARS}).",
    },
    "angel_one": {
        "label": "Angel One",
        "needs": {
            "ANGEL_ONE_API_KEY": "angel_one_api_key",
            "ANGEL_ONE_CLIENT_CODE": "angel_one_client_code",
            "ANGEL_ONE_PIN": "angel_one_pin",
            "ANGEL_ONE_TOTP_SECRET": "angel_one_totp_secret",
        },
        "note": "Logs in with your API key, client code, PIN and TOTP. About 400 days of daily history.",
    },
}


class SourceNotConfigured(Exception):
    pass


def current_settings() -> Settings:
    """A fresh read of .env (plus the environment), so a newly added token is seen at once."""
    return Settings()


def missing_settings(source: str, settings: Settings) -> list[str]:
    return [name for name, field in SOURCES[source]["needs"].items() if not getattr(settings, field)]


def source_status() -> list[dict]:
    """Which sources are set up. Reports only the *names* of settings that are missing, never values."""
    settings = current_settings()
    return [
        {
            "key": key,
            "label": info["label"],
            "configured": not missing_settings(key, settings),
            "missing": missing_settings(key, settings),
            "note": info["note"],
        }
        for key, info in SOURCES.items()
    ]


def open_adapter(source: str, years: int | None = None) -> tuple[MarketDataAdapter, Callable[[], None]]:
    """A ready-to-use adapter for `source` and a function to call when finished with it (Angel
    One logs in here and out there). Raises SourceNotConfigured if .env lacks what it needs."""
    settings = current_settings()
    missing = missing_settings(source, settings)
    if missing:
        raise SourceNotConfigured(
            f"{SOURCES[source]['label']} isn't set up: add {', '.join(missing)} to your local .env file."
        )
    if source == "upstox":
        adapter = UpstoxMarketDataAdapter(settings.upstox_analytics_token, history_days=(years or DEFAULT_YEARS) * 365)
        return adapter, lambda: None

    adapter = AngelOneMarketDataAdapter(
        settings.angel_one_api_key, settings.angel_one_client_code, settings.angel_one_pin, settings.angel_one_totp_secret
    )
    adapter.auth.login()
    return adapter, adapter.auth.logout


@dataclass
class ImportOutcome:
    symbol: str
    ok: bool
    name: str | None = None
    candles: int | None = None
    first_date: date | None = None
    last_date: date | None = None
    current_price: float | None = None
    error: str | None = None
    data_quality: dict | None = None


def import_symbols(
    db: Session, adapter: MarketDataAdapter, symbols: list[str], *, source: str, merge: bool = False
) -> list[ImportOutcome]:
    """Import each symbol separately, committing the ones that work, so one unknown symbol is
    reported without stopping the rest. A rejected token stops the batch, since it would fail
    every remaining symbol the same way."""
    known_names = {s["symbol"]: s["name"] for s in REAL_STOCKS}
    outcomes: list[ImportOutcome] = []
    stopped: str | None = None

    for symbol in symbols:
        if stopped:
            outcomes.append(ImportOutcome(symbol, False, error=f"Not tried: {stopped}"))
            continue
        try:
            name = known_names.get(symbol)
            exists = db.query(Stock).filter(Stock.symbol == symbol).first() is not None
            if name is None and not exists and hasattr(adapter, "instrument_name"):
                name = adapter.instrument_name(symbol)  # only names a new stock; never renames one
            stock = import_real_stock(db, adapter, symbol, name, source=source, replace=not merge)
            db.commit()
        except (StockNotFoundError, UpstoxError, AngelOneAuthError, ValueError, httpx.HTTPError) as err:
            db.rollback()
            outcomes.append(ImportOutcome(symbol, False, error=str(err) or type(err).__name__))
            if getattr(err, "auth_failed", False):
                stopped = "the token was rejected."
            continue

        count, first, last = (
            db.query(func.count(PriceData.id), func.min(PriceData.timestamp), func.max(PriceData.timestamp))
            .filter(PriceData.stock_id == stock.id)
            .one()
        )
        outcomes.append(
            ImportOutcome(
                stock.symbol,
                True,
                stock.name,
                count,
                first.date(),
                last.date(),
                stock.current_price,
                data_quality=data_quality_service.summary(db, stock),
            )
        )
    return outcomes
