"""Standalone smoke test for the Angel One (SmartAPI) market data adapter.

Fill in ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_CODE, ANGEL_ONE_PIN and ANGEL_ONE_TOTP_SECRET
in your own .env first (never commit real values -- .env is gitignored). This script makes
real calls against your Angel One account: it logs in, resolves an instrument token, and
reads a price quote and some historical candles. It never places, modifies or cancels an
order -- this project never calls those endpoints.

Usage:
    python scripts/test_angel_one_adapter.py [SYMBOL]

SYMBOL defaults to RELIANCE. Must be a plain NSE equity trading symbol (e.g. TCS, INFY),
not an exchange-qualified one like "TCS-EQ" -- the adapter adds that suffix itself.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.adapters.angel_one import AngelOneMarketDataAdapter  # noqa: E402
from backend.app.config import settings  # noqa: E402


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"

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

    adapter = AngelOneMarketDataAdapter(
        settings.angel_one_api_key,
        settings.angel_one_client_code,
        settings.angel_one_pin,
        settings.angel_one_totp_secret,
    )

    try:
        print(f"Logging in as {settings.angel_one_client_code}...")
        adapter.auth.login()
        print("Login OK.")

        print(f"Resolving instrument token for {symbol}...")
        token = adapter.resolve_instrument_token(symbol)
        print(f"{symbol} -> token {token}")

        print(f"Fetching latest price for {symbol}...")
        ltp = adapter.get_latest_price(symbol)
        print(f"LTP: {ltp}")

        print(f"Fetching the last 10 daily candles for {symbol}...")
        candles = adapter.get_historical_candles(symbol, limit=10)
        for c in candles:
            print(f"  {c.date}  O {c.open:.2f}  H {c.high:.2f}  L {c.low:.2f}  C {c.close:.2f}  V {c.volume}")
    finally:
        adapter.auth.logout()
        print("Logged out.")


if __name__ == "__main__":
    main()
