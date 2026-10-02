"""Standalone smoke test for the Upstox market data adapter.

Put UPSTOX_ANALYTICS_TOKEN in your own .env first (never commit real values -- .env is
gitignored; Upstox's Developer Apps page -> Analytics tab -> Generate Token). This makes real
read-only calls: it downloads Upstox's public instrument list, resolves a symbol to its
instrument key, and reads daily candles. The token can't place orders and this never tries to.

Usage:
    python scripts/test_upstox_adapter.py [SYMBOL]

SYMBOL defaults to RELIANCE and must be a plain NSE equity trading symbol (TCS, INFY, M&M).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.adapters.upstox import UpstoxError, UpstoxMarketDataAdapter  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.services.exceptions import StockNotFoundError  # noqa: E402


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    if not settings.upstox_analytics_token:
        sys.exit("Missing from .env: UPSTOX_ANALYTICS_TOKEN")

    adapter = UpstoxMarketDataAdapter(settings.upstox_analytics_token)
    try:
        print(f"Resolving the instrument key for {symbol}...")
        print(f"{symbol} -> {adapter.resolve_instrument_key(symbol)}")

        print("Fetching five years of daily candles...")
        candles = adapter.get_historical_candles(symbol)
        if not candles:
            sys.exit("Upstox returned no candles for that symbol.")
        print(f"{len(candles)} candles, {candles[0].date} to {candles[-1].date}. The last five:")
        for c in candles[-5:]:
            print(f"  {c.date}  O {c.open:.2f}  H {c.high:.2f}  L {c.low:.2f}  C {c.close:.2f}  V {c.volume}")
        print(f"Latest close: {adapter.get_latest_price(symbol)}")
    except (StockNotFoundError, UpstoxError) as err:
        sys.exit(f"Failed: {err}")


if __name__ == "__main__":
    main()
