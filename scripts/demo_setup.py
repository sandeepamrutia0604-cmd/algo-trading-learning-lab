"""Build a self-contained demo database, so the app can be shown (or recorded) from a known, good state.

The demo uses only the app's own simulated stocks, so it needs no broker login, no .env and no
imported market data, and anyone who clones the repo can rebuild it. It is written to its own file
and never touches your real database:

    python scripts/demo_setup.py                 # writes data/demo.db
    python scripts/demo_setup.py --out some.db   # or somewhere else

Then run the app on it (PowerShell; the real database stays untouched):

    $env:DATABASE_URL = "sqlite:///./data/demo.db"
    .venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --port 8001

What it sets up:
  * about three years of simulated history for ALPHA, BETA, GAMMA and DELTA, plus a practice stock, ZETA
    (a long history is what backtests, the optimiser and walk-forward testing need)
  * BADDATA: a stock imported from "a file" with deliberate problems (an unadjusted split and a missing
    fortnight), so the Data quality tab has something to catch
  * three saved strategies with their signals marked, a few finished paper trades so the Performance and
    Journal pages have something to show, and one open position protected by a stop-loss and take-profit
  * trading costs switched on, as a real account would have them
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.app import models  # noqa: E402,F401  (registers every table)
from backend.app.adapters.base import Candle  # noqa: E402
from backend.app.config import Settings  # noqa: E402
from backend.app.db import Base  # noqa: E402
from backend.app.models import PriceData, Stock  # noqa: E402
from backend.app.services import (  # noqa: E402
    backtest_service,
    cost_service,
    market_service,
    practice_stocks,
    scanner_service,
    strategy_service,
    trading_service,
)
from backend.app.services.real_stocks import import_candles  # noqa: E402
from backend.app.services.seed import ensure_seed_data  # noqa: E402

HISTORY_DAYS = 760  # business days of simulated history: about three years
SEED = 7
# Gentler trends than the app's defaults, which compound to a twenty-fold rise over three years.
BETA_BEHAVIOUR = ("trending", 0.018, 0.0006)
ZETA_BEHAVIOUR = ("trending", 0.015, 0.0003)
# Strategies the scanner tries, in order, when looking for a day that has a BUY signal in it.
SCAN_CANDIDATES = (
    ("breakout", {"lookback": 20, "exit_lookback": 10}),
    ("ma_crossover", {"fast": 10, "slow": 30}),
    ("mean_reversion", None),
    ("bollinger", None),
)


def real_database_path() -> Path:
    url = Settings().database_url
    return Path(url.replace("sqlite:///", "", 1)).resolve()


def bad_data_candles(db) -> list[Candle]:
    """A made-up stock with two classic data problems, cut from ALPHA's history and ending long before
    the market clock, so it never holds back the clock: from day 220 its prices are halved with no
    adjustment (what a split looks like when only one data source adjusted for it), and a fortnight
    of days is missing."""
    alpha = db.query(Stock).filter(Stock.symbol == "ALPHA").one()
    rows = (
        db.query(PriceData).filter(PriceData.stock_id == alpha.id).order_by(PriceData.timestamp).limit(420).all()
    )
    candles = []
    for i, row in enumerate(rows):
        if 300 <= i < 310:
            continue  # ten missing weekdays
        factor = 0.5 if i >= 220 else 1.0
        candles.append(
            Candle(
                date=row.timestamp.date(),
                open=round(row.open * factor, 2),
                high=round(row.high * factor, 2),
                low=round(row.low * factor, 2),
                close=round(row.close * factor, 2),
                volume=row.volume,
            )
        )
    return candles


def trade_round(db, symbol: str, quantity: int, hold_days: int) -> None:
    """Buy, let the market run, then sell: one finished trade for the Journal."""
    trading_service.execute_buy(db, symbol, quantity, reason="Manual trade")
    market_service.advance(db, hold_days)
    trading_service.execute_sell(db, symbol, quantity, reason="Manual trade")


def todays_buy(db) -> tuple[str, str] | None:
    """(strategy name, symbol) for the first scanner candidate that has a BUY signal on the market date."""
    for kind, params in SCAN_CANDIDATES:
        defn, clean = backtest_service.resolve_definition(kind, params)
        for row in scanner_service.scan(db, defn, clean):
            if row["signal_today"] and row["signal_today"]["side"] == "BUY" and row["symbol"] != "BADDATA":
                return defn.name_fn(clean), row["symbol"]
    return None


def build(out: Path) -> None:
    if out.resolve() == real_database_path():
        sys.exit(f"Refusing to overwrite your real database ({out}). Pick a different --out.")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    engine = create_engine(f"sqlite:///{out}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    ensure_seed_data(db, with_history=False)
    market_service.update_config(db, "BETA", *BETA_BEHAVIOUR)
    market_service.generate_all(db, HISTORY_DAYS, seed=SEED)
    practice_stocks.create(db, "ZETA", "Zeta Pharma", 320.0, *ZETA_BEHAVIOUR, seed=SEED)

    import_candles(db, "BADDATA", "Sample with data problems", bad_data_candles(db), source="csv", replace=True)
    db.commit()

    cost_service.update_settings(db, enabled=True)

    for symbol, kind, params, quantity, name in (
        ("BETA", "ma_crossover", {"fast": 20, "slow": 50}, 20, "BETA trend follower"),
        ("DELTA", "breakout", {"lookback": 20, "exit_lookback": 10}, 10, "DELTA breakout"),
        ("GAMMA", "mean_reversion", None, 30, "GAMMA bounce"),
    ):
        strategy = strategy_service.create_strategy(db, symbol, params, quantity, name=name, type_key=kind)
        strategy_service.run_on_history(db, strategy)

    # A little trading history, so the Journal and Performance pages have something to show.
    trade_round(db, "BETA", 20, 9)
    trade_round(db, "GAMMA", 40, 6)
    trade_round(db, "DELTA", 10, 7)
    trade_round(db, "ALPHA", 30, 8)
    trade_round(db, "ZETA", 15, 5)

    # Run the market on until some strategy has a BUY signal today, so the Scanner opens on something to see.
    found = todays_buy(db)
    for _ in range(60):
        if found:
            break
        market_service.advance(db, 1)
        found = todays_buy(db)
    print(f"Scanner BUY today: {found[0]} on {found[1]}" if found else "No scanner BUY found within 60 days.")

    # One open position, protected, for the Trade page to open on.
    stock = db.query(Stock).filter(Stock.symbol == "BETA").one()
    price = stock.current_price
    trading_service.execute_buy(
        db, "BETA", 15, stop_price=round(price * 0.96, 2), target_price=round(price * 1.08, 2)
    )

    print(f"Wrote {out}")
    print(
        f"Market date {market_service.latest_market_date(db)}; {db.query(Stock).count()} stocks; "
        f"{db.query(models.Trade).count()} trades."
    )
    db.close()
    engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a self-contained demo database from simulated stocks.")
    parser.add_argument("--out", type=Path, default=Path("data/demo.db"), help="where to write it (default data/demo.db)")
    args = parser.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
