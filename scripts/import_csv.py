"""Import a stock's daily candles from a CSV/TSV file -- no broker login, API key, or .env needed.

The file's first row must name the columns (Date, Open, High, Low, Close, Volume). Delimiter
(tab, comma, semicolon), date format (01 Oct 2026, 2026-10-01, 01/10/2026 ...), thousands
separators (1,180.1) and row order (newest first is fine) are all handled. A pasted table from
a broker's chatbot works once saved to a text file.

Usage:
    python scripts/import_csv.py SYMBOL FILE [--name "Reliance Industries"] [--replace]

By default the file is merged into whatever history the stock already has (rows are matched by
date), so a short file adds its days without touching the rest. --replace discards the
existing history first. Simulated stocks (ALPHA, BETA, GAMMA, DELTA) can't be imported over.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.adapters.csv_candles import CsvImportError, load_candles  # noqa: E402
from backend.app.db import Base, SessionLocal, engine  # noqa: E402
from backend.app.migrations import ensure_columns  # noqa: E402
from backend.app.models import PriceData  # noqa: E402
from backend.app.services.real_stocks import import_candles  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import daily candles for a stock from a CSV/TSV file.")
    parser.add_argument("symbol", help="Trading symbol, e.g. RELIANCE")
    parser.add_argument("file", type=Path, help="Path to the CSV/TSV file")
    parser.add_argument("--name", help="Display name for a new stock (defaults to the symbol)")
    parser.add_argument("--replace", action="store_true", help="Discard the stock's existing history first")
    args = parser.parse_args()

    try:
        candles = load_candles(args.file)
    except (OSError, CsvImportError) as err:
        print(f"Couldn't read {args.file}: {err}")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)

    db = SessionLocal()
    try:
        stock = import_candles(db, args.symbol, args.name, candles, source="csv", replace=args.replace)
        db.commit()
        total = db.query(PriceData).filter(PriceData.stock_id == stock.id).count()
        print(
            f"{stock.symbol}: read {len(candles)} candles ({candles[0].date} to {candles[-1].date}); "
            f"{total} candles now stored, current price {stock.current_price}"
        )
    except ValueError as err:
        db.rollback()
        print(err)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
