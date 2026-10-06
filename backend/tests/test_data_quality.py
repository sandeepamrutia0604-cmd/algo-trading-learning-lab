from datetime import date, datetime, timedelta

import pytest

from backend.app.adapters.base import Candle
from backend.app.engine import data_quality as dq
from backend.app.models import PriceData, Stock

MONDAY = date(2026, 1, 5)


def weekdays(n: int, start: date = MONDAY) -> list[date]:
    days, day = [], start
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def candle(day: date, close: float, *, spread: float = 1.0, volume: int = 1000) -> Candle:
    """A normal-looking candle: opens at the close, a little room above and below."""
    return Candle(day, close, close + spread, close - spread, close, volume)


def series(closes: list[float], start: date = MONDAY) -> list[Candle]:
    return [candle(d, c) for d, c in zip(weekdays(len(closes), start), closes)]


def calm(n: int = 300) -> list[Candle]:
    """n days drifting gently up and down, nothing unusual."""
    return series([100 + (i % 7) * 0.5 + i * 0.05 for i in range(n)])


def kinds(issues):
    return [i.kind for i in issues]


# ---------- a healthy history ----------


def test_a_calm_history_has_no_issues():
    issues = dq.scan(calm())
    assert issues == []
    assert dq.status(issues) == "clean"


def test_an_empty_history_has_nothing_to_report():
    assert dq.scan([]) == []


# ---------- impossible prices ----------


def test_a_high_below_the_low_is_an_error():
    candles = calm()
    candles[10] = Candle(candles[10].date, 100, 98, 102, 100, 1000)
    issues = dq.scan(candles)
    assert [(i.kind, i.severity, i.date) for i in issues] == [("bad_ohlc", "error", candles[10].date)]
    assert dq.status(issues) == "problems"


def test_a_high_below_the_close_is_an_error():
    candles = calm()
    candles[5] = Candle(candles[5].date, 100, 100.5, 99, 101, 1000)
    assert kinds(dq.scan(candles)) == ["bad_ohlc"]


def test_a_low_above_the_open_is_an_error():
    candles = calm()
    candles[5] = Candle(candles[5].date, 100, 103, 101, 102, 1000)
    assert kinds(dq.scan(candles)) == ["bad_ohlc"]


def test_a_zero_price_is_an_error_and_not_also_reported_as_a_jump():
    candles = calm()
    candles[20] = Candle(candles[20].date, 100, 101, 0, 100, 1000)
    issues = dq.scan(candles)
    assert [(i.kind, i.severity) for i in issues] == [("non_positive", "error")]


def test_a_zero_close_does_not_crash_the_jump_check():
    candles = calm()
    candles[20] = Candle(candles[20].date, 0, 0, 0, 0, 0)
    assert "non_positive" in kinds(dq.scan(candles))


def test_an_unusually_wild_day_is_a_warning():
    candles = calm()
    candles[30] = Candle(candles[30].date, 100, 130, 100, 105, 1000)  # high is 30% above low
    issues = dq.scan(candles)
    assert [(i.kind, i.severity) for i in issues] == [("wide_range", "warning")]
    assert issues[0].value == pytest.approx(30.0)


# ---------- big moves and splits ----------


def test_a_move_just_under_the_threshold_is_not_flagged():
    closes = [100.0 + (i % 3) * 0.1 for i in range(250)] + [119.0] * 50  # +19% on the 251st day
    assert dq.scan(series(closes)) == []


def test_a_big_one_day_move_is_flagged_with_its_size_and_date():
    closes = [100 + (i % 3) * 0.1 for i in range(150)] + [128.0] + [128 + (i % 3) * 0.1 for i in range(149)]
    candles = series(closes)
    issues = dq.scan(candles)
    assert [(i.kind, i.severity, i.date) for i in issues] == [("big_jump", "warning", candles[150].date)]
    assert issues[0].value == pytest.approx((128 / closes[149] - 1) * 100)


def test_a_big_fall_is_flagged_too():
    closes = [100.0 + (i % 3) * 0.1 for i in range(150)] + [76.0] * 150
    issues = dq.scan(series(closes))
    assert [i.kind for i in issues] == ["big_jump"]
    assert issues[0].value < -20


@pytest.mark.parametrize("ratio", [0.5, 1 / 3, 0.25, 0.2, 0.1, 2 / 3])
def test_a_drop_matching_a_split_or_bonus_ratio_is_called_a_possible_split(ratio):
    closes = [1000.0] * 150 + [1000.0 * ratio] * 150
    issues = dq.scan(series(closes))
    assert kinds(issues) == ["possible_split"]
    assert "split" in issues[0].message


def test_the_fake_half_price_day_is_found():
    """The -49.8% day that appeared when raw and adjusted prices were joined."""
    closes = [2000.0] * 100 + [2000.0 * 0.502] * 200
    issues = dq.scan(series(closes))
    assert kinds(issues) == ["possible_split"]
    assert issues[0].value == pytest.approx(-49.8)


def test_a_reverse_split_is_recognised():
    closes = [100.0] * 150 + [1000.0] * 150  # x10
    issues = dq.scan(series(closes))
    assert kinds(issues) == ["possible_split"]
    assert "reverse split" in issues[0].message


def test_a_big_drop_that_matches_no_ratio_is_just_a_big_jump():
    closes = [100.0] * 150 + [58.0] * 150  # -42%: nothing like 1/2 or 2/3
    assert kinds(dq.scan(series(closes))) == ["big_jump"]


def test_a_move_between_20_and_30_percent_is_never_called_a_split():
    # x0.8 is a 1-for-4 *bonus* ratio, but 20% is a normal limit-down day; only bigger moves are checked
    assert kinds(dq.scan(series([100.0] * 150 + [79.0] * 150))) == ["big_jump"]


# ---------- dates ----------


def test_a_saturday_candle_is_info_only():
    candles = calm()
    saturday = Candle(date(2026, 1, 10), 100, 101, 99, 100, 1000)
    candles = candles[:5] + [saturday] + candles[5:]  # Jan 5-9 are Mon-Fri, then the Saturday
    issues = dq.scan(candles)
    assert [(i.kind, i.severity) for i in issues if i.kind == "weekend_candle"] == [("weekend_candle", "info")]
    assert dq.status(issues) == "clean"


def test_a_holiday_sized_gap_is_info():
    candles = calm()
    del candles[50:53]  # three weekdays missing
    issues = [i for i in dq.scan(candles) if i.kind == "missing_days"]
    assert [(i.severity, i.value) for i in issues] == [("info", 3.0)]


def test_one_or_two_missing_weekdays_are_ordinary_holidays():
    candles = calm()
    del candles[50:52]
    assert "missing_days" not in kinds(dq.scan(candles))


def test_a_long_gap_is_a_warning():
    candles = calm()
    del candles[100:110]  # ten weekdays missing
    issues = [i for i in dq.scan(candles) if i.kind == "missing_days"]
    assert [(i.severity, i.value) for i in issues] == [("warning", 10.0)]
    assert issues[0].date == candles[100].date  # the first day back


def test_weekends_inside_a_gap_are_not_counted_as_missing():
    # Friday to the following Wednesday: Mon and Tue are missing, the weekend is not
    candles = [candle(date(2026, 1, 9), 100), candle(date(2026, 1, 14), 100)]
    assert dq._weekdays_between(candles[0].date, candles[1].date) == 2


# ---------- flat runs and volume ----------


def test_a_run_of_unmoving_candles_is_a_warning_reported_once():
    candles = calm()
    for i in range(60, 66):
        candles[i] = Candle(candles[i].date, 120.0, 120.0, 120.0, 120.0, 0)
    issues = [i for i in dq.scan(candles) if i.kind == "flat_run"]
    assert len(issues) == 1
    assert (issues[0].severity, issues[0].value, issues[0].date) == ("warning", 6.0, candles[60].date)


def test_a_flat_stretch_at_the_very_end_is_reported():
    candles = calm()
    for i in range(len(candles) - 4, len(candles)):
        candles[i] = Candle(candles[i].date, 120.0, 120.0, 120.0, 120.0, 500)
    assert [i.value for i in dq.scan(candles) if i.kind == "flat_run"] == [4.0]


def test_two_flat_days_are_not_enough():
    candles = calm()
    for i in (60, 61):
        candles[i] = Candle(candles[i].date, 120.0, 120.0, 120.0, 120.0, 500)
    assert "flat_run" not in kinds(dq.scan(candles))


def test_flat_candles_at_different_prices_are_not_one_run():
    candles = calm()
    for i, price in zip(range(60, 66), (120, 121, 120, 121, 120, 121)):
        candles[i] = Candle(candles[i].date, price, price, price, price, 500)
    assert "flat_run" not in kinds(dq.scan(candles))


def test_scattered_zero_volume_days_are_info_with_a_count():
    candles = calm()
    for i in (10, 50, 90):
        c = candles[i]
        candles[i] = Candle(c.date, c.open, c.high, c.low, c.close, 0)
    issues = [i for i in dq.scan(candles) if i.kind == "zero_volume"]
    assert [(i.severity, i.value, i.date) for i in issues] == [("info", 3.0, candles[10].date)]


def test_a_file_with_no_volume_at_all_is_one_note():
    candles = [Candle(c.date, c.open, c.high, c.low, c.close, 0) for c in calm()]
    issues = dq.scan(candles)
    assert [(i.kind, i.severity) for i in issues] == [("no_volume", "info")]


# ---------- length ----------


def test_a_short_history_is_a_warning():
    issues = dq.scan(series([100 + i * 0.1 for i in range(40)]))
    assert [(i.kind, i.severity, i.value) for i in issues] == [("short_history", "warning", 40.0)]


def test_under_a_year_is_a_note():
    issues = dq.scan(series([100 + (i % 7) * 0.5 for i in range(247)]))
    assert [(i.kind, i.severity, i.value) for i in issues] == [("short_history", "info", 247.0)]
    assert dq.status(issues) == "clean"


# ---------- ordering and status ----------


def test_issues_come_back_most_serious_first_then_by_date():
    candles = calm()
    candles[200] = Candle(candles[200].date, 100, 98, 102, 100, 1000)  # error
    candles[20] = Candle(candles[20].date, 100, 135, 100, 105, 1000)  # warning
    candles[10] = Candle(candles[10].date, 100, 101, 99, 100, 0)  # zero volume: info
    issues = dq.scan(candles)
    assert [i.severity for i in issues] == ["error", "warning", "info"]


def test_status_is_check_when_there_are_only_warnings_and_problems_with_any_error():
    warning = dq.Issue("big_jump", "warning", "x")
    error = dq.Issue("bad_ohlc", "error", "x")
    info = dq.Issue("short_history", "info", "x")
    assert dq.status([info]) == "clean"
    assert dq.status([info, warning]) == "check"
    assert dq.status([info, warning, error]) == "problems"
    assert dq.counts([info, warning, warning, error]) == {"error": 1, "warning": 2, "info": 1}


# ---------- through the API ----------


def add_stock(db, symbol, candles, source="csv"):
    stock = Stock(symbol=symbol, name=symbol, source=source, starting_price=candles[0].close, current_price=candles[-1].close)
    db.add(stock)
    db.flush()
    for c in candles:
        db.add(
            PriceData(
                stock_id=stock.id,
                timestamp=datetime.combine(c.date, datetime.min.time()),
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
        )
    db.commit()
    return stock


def test_the_report_lists_every_issue_with_its_summary(client, db_session):
    candles = calm()
    candles = candles[:150] + [Candle(c.date, c.open / 2, c.high / 2, c.low / 2, c.close / 2, c.volume) for c in candles[150:]]
    add_stock(db_session, "SPLITCO", candles)

    body = client.get("/api/data-quality/splitco").json()

    assert (body["symbol"], body["source"], body["candles"], body["status"]) == ("SPLITCO", "csv", 300, "check")
    assert (body["errors"], body["warnings"], body["infos"]) == (0, 1, 0)
    assert body["first_date"] == str(candles[0].date) and body["last_date"] == str(candles[-1].date)
    assert [(i["kind"], i["date"]) for i in body["issues"]] == [("possible_split", str(candles[150].date))]
    assert "split" in body["issues"][0]["message"]


def test_the_scan_covers_candles_the_market_clock_has_not_reached(client, db_session):
    client.post("/api/market/generate", json={"days": 80, "seed": 3})
    candles = calm()
    add_stock(db_session, "LONGCO", candles)  # all 300 days stored, the clock is far behind

    assert client.get("/api/data-quality/LONGCO").json()["candles"] == 300


def test_the_list_gives_a_summary_per_stock_without_the_issues(client, db_session):
    client.post("/api/market/generate", json={"days": 80, "seed": 3})
    add_stock(db_session, "CLEANCO", calm())

    rows = {r["symbol"]: r for r in client.get("/api/data-quality").json()}

    assert {"ALPHA", "BETA", "GAMMA", "DELTA", "CLEANCO"} <= set(rows)
    assert rows["CLEANCO"]["status"] == "clean"
    assert all("issues" not in r for r in rows.values())
    assert rows["ALPHA"]["source"] == "simulated"


def test_an_unknown_symbol_is_a_404(client):
    assert client.get("/api/data-quality/NOPE").status_code == 404


def test_the_scan_changes_nothing(client, db_session):
    candles = calm()
    add_stock(db_session, "KEEPCO", candles)
    before = db_session.query(PriceData).count()

    client.get("/api/data-quality")
    client.get("/api/data-quality/KEEPCO")

    assert db_session.query(PriceData).count() == before


def test_a_csv_import_reports_how_the_data_looks(client):
    rows = ["Date,Open,High,Low,Close,Volume"]
    for i, d in enumerate(weekdays(80)):
        close = 100 + (i % 5) * 0.4
        rows.append(f"{d.isoformat()},{close},{close + 1},{close - 1},{close},1000")
    body = client.post("/api/stocks/import", json={"symbol": "NEWCO", "csv_text": "\n".join(rows), "replace": True}).json()

    quality = body["data_quality"]
    assert (quality["symbol"], quality["candles"], quality["status"]) == ("NEWCO", 80, "clean")
    assert quality["infos"] == 1  # under a year of history
