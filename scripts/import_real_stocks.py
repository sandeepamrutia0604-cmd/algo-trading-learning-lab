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

from backend.app.adapters.angel_one_auth import AngelOneAuthError  # noqa: E402
from backend.app.db import Base, SessionLocal, engine  # noqa: E402
from backend.app.migrations import ensure_columns  # noqa: E402
from backend.app.services import data_sources  # noqa: E402
from backend.app.services.real_stocks import REAL_STOCKS  # noqa: E402


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
        if not 1 <= args.years <= data_sources.MAX_YEARS:
            parser.error(f"--years must be between 1 and {data_sources.MAX_YEARS}")

    symbols = [s.upper() for s in args.symbols] or [s["symbol"] for s in REAL_STOCKS]

    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)

    try:
        adapter, close = data_sources.open_adapter(args.source, args.years)
    except (data_sources.SourceNotConfigured, AngelOneAuthError) as err:
        sys.exit(str(err))

    db = SessionLocal()
    try:
        outcomes = data_sources.import_symbols(db, adapter, symbols, source=args.source, merge=args.merge)
    finally:
        close()
        db.close()

    for o in outcomes:
        if o.ok:
            print(f"  {o.symbol}: {o.name} -- {o.candles} candles ({o.first_date} to {o.last_date}), current price {o.current_price}")
        else:
            print(f"  {o.symbol}: NOT IMPORTED -- {o.error}")

    failed = [o.symbol for o in outcomes if not o.ok]
    if failed:
        sys.exit(f"{len(failed)} of {len(outcomes)} stock(s) were not imported: {', '.join(failed)}")


if __name__ == "__main__":
    main()
