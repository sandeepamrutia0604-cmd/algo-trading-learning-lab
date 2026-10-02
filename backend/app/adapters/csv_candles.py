"""Parse daily OHLCV candles out of a CSV/TSV export -- a broker chatbot table pasted into a
text file, a TradingView/Yahoo/NSE download, etc. -- so market data can come from a file the
user fetched themselves, with no broker credentials involved.

Deliberately tolerant about layout (delimiter, header spelling, date format, thousands
separators, row order) and strict about content: a row that can't be read is an error with its
line number, never silently skipped, since a dropped candle would quietly distort every
indicator and backtest built on it.
"""

import csv
import io
from datetime import date, datetime
from pathlib import Path

from .base import Candle


class CsvImportError(ValueError):
    pass


# "Adj Close" and "Last" are intentionally not aliases for close: the first is dividend-adjusted
# and the second is the last traded price, so neither is the day's closing price.
_ALIASES = {
    "date": {"date", "timestamp", "time", "datetime", "day"},
    "open": {"open", "o", "open price"},
    "high": {"high", "h", "high price"},
    "low": {"low", "l", "low price"},
    "close": {"close", "c", "close price", "closing price"},
    "volume": {"volume", "vol", "qty", "shares traded", "total traded quantity", "traded quantity"},
}
_REQUIRED = ("date", "open", "high", "low", "close")

# Day-first only: "01/10/2026" is read as 1 October, never January 10 (Indian convention).
_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d-%b-%y", "%d %b %y")


def _delimiter(sample_line: str) -> str:
    # Checked in this order because a pasted table is tab-separated *and* its numbers contain commas.
    if "\t" in sample_line:
        return "\t"
    return ";" if sample_line.count(";") > sample_line.count(",") else ","


def _parse_date(text: str, line: int) -> date:
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        raise CsvImportError(f"Line {line}: can't read the date '{text}'") from None


def _parse_number(text: str, field: str, line: int) -> float:
    cleaned = text.replace("₹", "").replace(",", "").replace('"', "").strip()
    try:
        return float(cleaned)
    except ValueError:
        raise CsvImportError(f"Line {line}: '{text}' isn't a number for {field}") from None


def _parse_volume(text: str, line: int) -> int:
    if text.strip() in ("", "-"):
        return 0
    return int(_parse_number(text, "volume", line))


def parse_candles(text: str) -> list[Candle]:
    """Candles from CSV/TSV text, oldest first, one per date (a repeated date keeps its last row)."""
    text = text.lstrip("﻿")
    first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not first_line:
        raise CsvImportError("The file is empty")

    reader = csv.reader(io.StringIO(text), delimiter=_delimiter(first_line))
    header = next(row for row in reader if any(cell.strip() for cell in row))

    columns: dict[str, int] = {}
    for index, cell in enumerate(header):
        name = cell.strip().lower()
        for field, aliases in _ALIASES.items():
            if name in aliases and field not in columns:
                columns[field] = index
    missing = [field for field in _REQUIRED if field not in columns]
    if missing:
        raise CsvImportError(
            f"Missing column(s): {', '.join(missing)}. Found headers: {', '.join(c.strip() for c in header)}. "
            "The first row must name the columns (Date, Open, High, Low, Close, Volume)."
        )

    by_date: dict[date, Candle] = {}
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        line = reader.line_num
        needed = max(columns.values())
        if len(row) <= needed:
            raise CsvImportError(f"Line {line}: expected at least {needed + 1} columns but found {len(row)}")

        values = {field: _parse_number(row[columns[field]], field, line) for field in _REQUIRED[1:]}
        if min(values.values()) <= 0:
            raise CsvImportError(f"Line {line}: prices must be above zero")
        day = _parse_date(row[columns["date"]], line)
        volume = _parse_volume(row[columns["volume"]], line) if "volume" in columns else 0
        by_date[day] = Candle(
            date=day, open=values["open"], high=values["high"], low=values["low"], close=values["close"], volume=volume
        )

    if not by_date:
        raise CsvImportError("The file has a header but no data rows")
    return [by_date[d] for d in sorted(by_date)]


def load_candles(path: Path | str) -> list[Candle]:
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")  # older Excel "CSV" exports
    return parse_candles(text)
