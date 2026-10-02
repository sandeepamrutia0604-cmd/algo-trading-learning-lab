from datetime import date

import pytest

from backend.app.adapters.csv_candles import CsvImportError, load_candles, parse_candles

# A table copied from Angel One's chatbot: tab-separated, "01 Oct 2026" dates, thousands
# separators in every number, newest row first.
PASTED_TABLE = (
    "Date\tOpen\tHigh\tLow\tClose\tVolume\n"
    "01 Oct 2026\t1,180.1\t1,183.9\t1,160.8\t1,167.7\t16,771,221\n"
    "30 Sep 2026\t1,182.0\t1,196.5\t1,181.7\t1,187.0\t16,376,789\n"
    "29 Sep 2026\t1,193.8\t1,198.3\t1,181.8\t1,182.0\t24,191,416\n"
)


def test_parses_a_pasted_broker_table_and_sorts_oldest_first():
    candles = parse_candles(PASTED_TABLE)

    assert [c.date for c in candles] == [date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)]
    last = candles[-1]
    assert (last.open, last.high, last.low, last.close, last.volume) == (1180.1, 1183.9, 1160.8, 1167.7, 16771221)


def test_parses_a_comma_csv_with_quoted_thousands_separators():
    text = 'Date,Open,High,Low,Close,Volume\n01 Oct 2026,"1,180.1","1,183.9","1,160.8","1,167.7","16,771,221"\n'
    candle = parse_candles(text)[0]
    assert (candle.open, candle.close, candle.volume) == (1180.1, 1167.7, 16771221)


def test_parses_a_yahoo_style_export_and_ignores_adj_close():
    text = "Date,Open,High,Low,Close,Adj Close,Volume\n2026-10-01,10,12,9,11,5.5,1000\n"
    candle = parse_candles(text)[0]
    assert candle.close == 11 and candle.volume == 1000


@pytest.mark.parametrize(
    "date_text", ["2026-10-01", "01-10-2026", "01/10/2026", "01 Oct 2026", "01-Oct-2026", "1 October 2026", "2026-10-01T00:00:00+05:30"]
)
def test_accepts_the_common_date_formats_day_first(date_text):
    assert parse_candles(f"date,open,high,low,close,volume\n{date_text},1,2,1,2,5\n")[0].date == date(2026, 10, 1)


def test_header_matching_ignores_case_and_column_order_and_semicolons_work():
    text = "VOLUME;CLOSE;LOW;HIGH;OPEN;DATE\n5;2;1;3;1;2026-10-01\n"
    candle = parse_candles(text)[0]
    assert (candle.open, candle.high, candle.low, candle.close, candle.volume) == (1, 3, 1, 2, 5)


def test_rupee_symbols_and_a_missing_volume_column_are_fine():
    text = 'Date,Open,High,Low,Close\n2026-10-01,"₹1,000","₹1,010","₹990","₹1,005"\n'
    candle = parse_candles(text)[0]
    assert (candle.open, candle.close, candle.volume) == (1000.0, 1005.0, 0)


def test_a_repeated_date_keeps_its_last_row():
    text = "date,open,high,low,close,volume\n2026-10-01,1,2,1,2,5\n2026-10-01,1,3,1,3,9\n"
    candles = parse_candles(text)
    assert len(candles) == 1 and candles[0].close == 3


def test_blank_lines_and_a_byte_order_mark_are_ignored():
    text = "﻿date,open,high,low,close,volume\n\n2026-10-01,1,2,1,2,5\n\n"
    assert len(parse_candles(text)) == 1


def test_missing_required_columns_are_named_in_the_error():
    with pytest.raises(CsvImportError, match="Missing column.*close"):
        parse_candles("date,open,high,low,volume\n2026-10-01,1,2,1,5\n")


def test_a_bad_number_reports_its_line():
    text = "date,open,high,low,close,volume\n2026-10-01,1,2,1,2,5\n2026-10-02,1,abc,1,2,5\n"
    with pytest.raises(CsvImportError, match="Line 3.*abc"):
        parse_candles(text)


def test_a_bad_date_reports_its_line():
    with pytest.raises(CsvImportError, match="Line 2.*date"):
        parse_candles("date,open,high,low,close,volume\nlast tuesday,1,2,1,2,5\n")


def test_zero_prices_are_rejected():
    with pytest.raises(CsvImportError, match="above zero"):
        parse_candles("date,open,high,low,close,volume\n2026-10-01,0,2,1,2,5\n")


def test_short_rows_are_rejected():
    with pytest.raises(CsvImportError, match="expected at least"):
        parse_candles("date,open,high,low,close,volume\n2026-10-01,1,2\n")


def test_empty_and_header_only_files_are_rejected():
    with pytest.raises(CsvImportError, match="empty"):
        parse_candles("  \n\n")
    with pytest.raises(CsvImportError, match="no data rows"):
        parse_candles("date,open,high,low,close,volume\n")


def test_load_candles_reads_a_file(tmp_path):
    path = tmp_path / "reliance.txt"
    path.write_text(PASTED_TABLE, encoding="utf-8")
    assert len(load_candles(path)) == 3


def test_load_candles_falls_back_to_cp1252_for_old_excel_exports(tmp_path):
    path = tmp_path / "old.csv"
    path.write_bytes("Date,Open,High,Low,Close,Volume,Note\n2026-10-01,1,2,1,2,5,café\n".encode("cp1252"))
    assert len(load_candles(path)) == 1
