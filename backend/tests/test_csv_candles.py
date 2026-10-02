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


# ---------- NSE "all series" downloads ----------

# The layout of NSE's historical-data download: quoted headers with trailing spaces, Indian
# digit grouping (1,67,71,221), day-Mon-year dates, and extra rows for other series on the
# same date -- BL (block deals) here, with open = high = low = close and a different volume.
NSE_FILE = (
    '"Symbol  ","Series  ","Date  ","Prev Close  ","Open Price  ","High Price  ","Low Price  ",'
    '"Last Price  ","Close Price  ","Average Price ","Total Traded Quantity  ","Turnover ₹  "\n'
    '"RELIANCE","EQ","05-Oct-2021","2,556.15","2,555.10","2,612.00","2,547.35","2,610.25","2,609.20","2,582.03","62,45,770","16,12,67,67,140.45"\n'
    '"RELIANCE","EQ","04-Oct-2021","2,523.70","2,553.00","2,574.85","2,537.05","2,558.00","2,556.15","2,556.97","50,38,910","12,88,43,46,776.35"\n'
    '"RELIANCE","BL","04-Oct-2021","2,076.85","2,523.70","2,523.70","2,523.70","2,523.70","2,523.70","2,523.70","27,05,236","6,82,72,04,093.20"\n'
)


def test_parses_an_nse_download_headers_indian_digit_grouping_and_dates():
    candles = parse_candles(NSE_FILE)

    assert [c.date for c in candles] == [date(2021, 10, 4), date(2021, 10, 5)]
    last = candles[-1]
    assert (last.open, last.high, last.low, last.close, last.volume) == (2555.10, 2612.0, 2547.35, 2609.20, 6245770)


def test_only_eq_rows_are_used_when_a_series_column_mixes_in_other_series():
    day = parse_candles(NSE_FILE)[0]  # 04-Oct-2021 appears as EQ and as BL, BL listed last

    assert (day.close, day.volume) == (2556.15, 5038910)  # the EQ row, not the block-deal row


def test_the_eq_row_wins_whichever_order_the_series_are_listed_in():
    lines = NSE_FILE.splitlines()
    reordered = "\n".join([lines[0], lines[3], lines[1], lines[2]])  # BL row first

    assert parse_candles(reordered)[0].close == 2556.15


def test_non_eq_rows_with_unreadable_values_are_ignored_not_fatal():
    broken_bl = NSE_FILE.replace('"2,523.70","2,523.70","2,523.70","2,523.70","2,523.70","2,523.70"', '"-","-","-","-","-","-"')

    assert len(parse_candles(broken_bl)) == 2


def test_a_file_with_a_series_column_but_no_eq_rows_keeps_what_it_has():
    only_be = NSE_FILE.replace('"EQ"', '"BE"').replace('"BL"', '"BE"')

    assert len(parse_candles(only_be)) == 2


def test_a_file_without_a_series_column_is_unaffected():
    text = "Date,Open,High,Low,Close,Volume\n2026-10-01,1,2,1,2,5\n"
    assert len(parse_candles(text)) == 1
