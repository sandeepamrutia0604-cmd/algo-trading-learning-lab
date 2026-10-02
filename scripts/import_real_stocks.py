"""Import real NSE stocks and their historical candles from a broker's data API into the app's
own database, so they show up in the UI (Trade/Strategies/Backtests dropdowns, charts, the home
watchlist) exactly like the simulated ALPHA/BETA/GAMMA/DELTA stocks -- no other code changes.

Two sources, chosen with --source (default angel_one):

  angel_one  needs ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_CODE, ANGEL_ONE_PIN and
             ANGEL_ONE_TOTP_SECRET in your own .env. About 400 days of history.
  upstox     needs only UPSTOX_ANALYTICS_TOKEN in your own .env (a read-only token from
             Upstox's Developer Apps page -> Analytics tab; no static IP). Five years by
             default; --years goes up to 10.

Never commit real values -- .env is gitignored. Either way this only reads data: it never
places, modifies or cancels an order.

Usage:
    python scripts/import_real_stocks.py                              # default list, Angel One
    python scripts/import_real_stocks.py --source upstox              # default list, Upstox
    python scripts/import_real_stocks.py --source upstox --years 8 RELIANCE TCS
    python scripts/import_real_stocks.py --source upstox --merge INFY # keep any older history

By default a stock's stored history is replaced by what the source returns (re-run to refresh).
--merge instead merges by date, so history the source didn't return -- say, years you imported
from a CSV -- is kept.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func  # noqa: E402

from backend.app.adapters.angel_one import AngelOneMarketDataAdapter  # noqa: E402
from backend.app.adapters.upstox import MAX_DAYS_PER_REQUEST, UpstoxError, UpstoxMarketDataAdapter  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.db import Base, SessionLocal, engine  # noqa: E402
from backend.app.migrations import ensure_columns  # noqa: E402
from backend.app.models import PriceData  # noqa: E402
from backend.app.services.exceptions import StockNotFoundError  # noqa: E402
from backend.app.services.real_stocks import REAL_STOCKS, import_real_stock  # noqa: E402


def missing_settings(pairs: list[tuple[str, str]]) -> list[str]:
    return [name for name, value in pairs if not value]


def build_angel_one():
    missing = missing_settings(
        [
            ("ANGEL_ONE_API_KEY", settings.angel_one_api_key),
            ("ANGEL_ONE_CLIENT_CODE", settings.angel_one_client_code),
            ("ANGEL_ONE_PIN", settings.angel_one_pin),
            ("ANGEL_ONE_TOTP_SECRET", settings.angel_one_totp_secret),
        ]
    )
    if missing:
        sys.exit(f"Missing from .env: {', '.join(missing)}")
    adapter = AngelOneMarketDataAdapter(
        settings.angel_one_api_key, settings.angel_one_client_code, settings.angel_one_pin, settings.angel_one_totp_secret
    )
    print(f"Logging in as {settings.angel_one_client_code}...")
    adapter.auth.login()
    print("Login OK.")
    return adapter, adapter.auth.logout


def build_upstox(years: int):
    if missing_settings([("UPSTOX_ANALYTICS_TOKEN", settings.upstox_analytics_token)]):
        sys.exit("Missing from .env: UPSTOX_ANALYTICS_TOKEN (Upstox Developer Apps page -> Analytics tab -> Generate Token)")
    return UpstoxMarketDataAdapter(settings.upstox_analytics_token, history_days=years * 365), lambda: None


def main() -> None:
    parser = argparse.ArgumentParser(description="Import real NSE stocks and their history into the app's database.")
    parser.add_argument("symbols", nargs="*", help="Trading symbols (default: the curated list in real_stocks.py)")
    parser.add_argument("--source", choices=["angel_one", "upstox"], default="angel_one")
    parser.add_argument("--years", type=int, help="Years of history to fetch (Upstox only; default 5, max 10)")
    parser.add_argument("--merge", action="store_true", help="Merge into existing history instead of replacing it")
    args = parser.parse_args()

    if args.years is not None:
        if args.source != "upstox":
            parser.error("--years only applies to --source upstox")
        if not 1 <= args.years <= MAX_DAYS_PER_REQUEST // 365:
            parser.error(f"--years must be between 1 and {MAX_DAYS_PER_REQUEST // 365}")

    known_names = {s["symbol"]: s["name"] for s in REAL_STOCKS}
    if args.symbols:
        stocks = [{"symbol": s.upper(), "name": known_names.get(s.upper())} for s in args.symbols]  # None keeps an existing name
    else:
        stocks = REAL_STOCKS

    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)

    adapter, cleanup = build_angel_one() if args.source == "angel_one" else build_upstox(args.years or 5)
    failures = []
    db = SessionLocal()
    try:
        for entry in stocks:
            try:
                stock = import_real_stock(
                    db, adapter, entry["symbol"], entry["name"], source=args.source, replace=not args.merge
                )
                db.commit()
            except (StockNotFoundError, UpstoxError, ValueError) as err:
                db.rollback()
                failures.append(entry["symbol"])
                print(f"  {entry['symbol']}: NOT IMPORTED -- {err}")
                continue
            count, first, last = (
                db.query(func.count(PriceData.id), func.min(PriceData.timestamp), func.max(PriceData.timestamp))
                .filter(PriceData.stock_id == stock.id)
                .one()
            )
            print(f"  {stock.symbol}: {stock.name} -- {count} candles ({first.date()} to {last.date()}), current price {stock.current_price}")
    finally:
        cleanup()
        db.close()

    if failures:
        sys.exit(f"{len(failures)} of {len(stocks)} stock(s) were not imported: {', '.join(failures)}")


if __name__ == "__main__":
    main()
