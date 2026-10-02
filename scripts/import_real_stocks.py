"""Import real NSE stocks and their historical candles from Angel One into the app's own
database, so they show up in the UI (Trade/Strategies/Backtests dropdowns, charts, the home
watchlist) exactly like the simulated ALPHA/BETA/GAMMA/DELTA stocks -- no other code changes.

Fill in ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_CODE, ANGEL_ONE_PIN and ANGEL_ONE_TOTP_SECRET in
your own .env first (never commit real values). This makes real calls against your Angel One
account to read historical candles -- it never places, modifies or cancels an order.

Usage:
    python scripts/import_real_stocks.py                  # the default curated list
    python scripts/import_real_stocks.py RELIANCE TCS      # specific symbols instead

Re-run any time to refresh an already-imported stock's price history.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.adapters.angel_one import AngelOneMarketDataAdapter  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.db import Base, SessionLocal, engine  # noqa: E402
from backend.app.migrations import ensure_columns  # noqa: E402
from backend.app.models import PriceData  # noqa: E402
from backend.app.services.real_stocks import REAL_STOCKS, import_all_real_stocks  # noqa: E402


def main() -> None:
    args = sys.argv[1:]
    known_names = {s["symbol"]: s["name"] for s in REAL_STOCKS}
    stocks = [{"symbol": s.upper(), "name": known_names.get(s.upper(), s.upper())} for s in args] if args else REAL_STOCKS

    missing = [
        name
        for name, value in [
            ("ANGEL_ONE_API_KEY", settings.angel_one_api_key),
            ("ANGEL_ONE_CLIENT_CODE", settings.angel_one_client_code),
            ("ANGEL_ONE_PIN", settings.angel_one_pin),
            ("ANGEL_ONE_TOTP_SECRET", settings.angel_one_totp_secret),
        ]
        if not value
    ]
    if missing:
        print(f"Missing from .env: {', '.join(missing)}")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)

    adapter = AngelOneMarketDataAdapter(
        settings.angel_one_api_key,
        settings.angel_one_client_code,
        settings.angel_one_pin,
        settings.angel_one_totp_secret,
    )

    db = SessionLocal()
    try:
        print(f"Logging in as {settings.angel_one_client_code}...")
        adapter.auth.login()
        print("Login OK.")

        imported = import_all_real_stocks(db, adapter, stocks)
        for stock in imported:
            candle_count = db.query(PriceData).filter(PriceData.stock_id == stock.id).count()
            print(f"  {stock.symbol}: {stock.name} -- {candle_count} candles, current price {stock.current_price}")
    finally:
        adapter.auth.logout()
        db.close()
        print("Logged out.")


if __name__ == "__main__":
    main()
