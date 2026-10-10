from datetime import date, timedelta

import pytest

from backend.app.adapters.base import Candle
from backend.app.engine import scanner
from backend.app.models import Position
from backend.app.services import market_service
from backend.app.services.real_stocks import import_candles
from backend.app.services.seed import ensure_seed_data
from backend.app.strategies.base import SignalEvent

WARM = market_service.WARMUP_DAYS


def event(index, side="BUY", headline="h"):
    return SignalEvent(index=index, side=side, headline=headline, checks=["why"], values={})


# ---------- reading one stock's signals ----------


def test_a_stock_the_strategy_has_never_signalled_on_has_nothing_to_report():
    reading = scanner.read([], 100)
    assert (reading.signal_today, reading.last_signal, reading.days_since, reading.state) == (None, None, None, "none")


def test_no_candles_means_nothing_to_report_even_with_events():
    assert scanner.read([event(0)], 0).state == "none"


def test_a_signal_on_the_latest_candle_is_a_signal_today():
    reading = scanner.read([event(10, "BUY"), event(49, "SELL")], 50)
    assert reading.signal_today.side == "SELL" and reading.signal_today.index == 49
    assert (reading.days_since, reading.state) == (0, "out")


def test_an_older_signal_is_the_last_signal_but_not_todays():
    reading = scanner.read([event(10, "SELL"), event(40, "BUY")], 50)
    assert reading.signal_today is None
    assert (reading.last_signal.index, reading.days_since, reading.state) == (40, 9, "in")


def test_the_state_follows_the_side_of_the_last_signal():
    assert scanner.read([event(5, "BUY")], 50).state == "in"
    assert scanner.read([event(5, "BUY"), event(20, "SELL")], 50).state == "out"


def test_events_out_of_order_still_find_the_latest():
    assert scanner.read([event(40, "BUY"), event(10, "SELL")], 50).last_signal.index == 40


# ---------- sorting ----------


def test_stocks_sort_buys_today_then_sells_today_then_recent_then_quiet():
    readings = {
        "quiet": scanner.read([], 50),
        "old": scanner.read([event(10)], 50),
        "recent": scanner.read([event(45)], 50),
        "sell_today": scanner.read([event(20), event(49, "SELL")], 50),
        "buy_today": scanner.read([event(49)], 50),
    }
    ordered = sorted(readings, key=lambda name: scanner.rank(readings[name]))
    assert ordered == ["buy_today", "sell_today", "recent", "old", "quiet"]


# ---------- through the API ----------


def closes_to_candles(closes, start=date(2025, 9, 1)):
    candles, day = [], start
    for close in closes:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        candles.append(Candle(date=day, open=close, high=close + 0.5, low=close - 0.5, close=close, volume=1000))
        day += timedelta(days=1)
    return candles


def wiggle(n, base=100.0):
    """n quiet days that never make a new high or low by much: 100.0, 100.2, 100.0, 99.8, ..."""
    return [base + (0.0, 0.2, 0.0, -0.2)[i % 4] for i in range(n)]


@pytest.fixture()
def stocks(client, db_session):
    """Four stocks whose breakout signals (20-day high to buy, 10-day low to sell) are known on the
    market date, which is day 60 of each: AAA breaks out today, BBB breaks down today (after buying
    earlier), CCC bought nine days ago and still holds, DDD never signals."""
    ensure_seed_data(db_session)
    today = WARM - 1  # index of the market date
    series = {
        "AAA": wiggle(today) + [110.0] + wiggle(70),
        "BBB": wiggle(40) + [110.0] * (today - 40) + [90.0] + wiggle(70),
        "CCC": wiggle(today - 9) + [110.0] * 10 + wiggle(70, 110.0),
        "DDD": wiggle(today + 71),
    }
    for symbol, closes in series.items():
        import_candles(db_session, symbol, f"{symbol} Ltd", closes_to_candles(closes), source="csv", replace=False)
    db_session.commit()
    return series


def scan(client, **body):
    response = client.post("/api/scanner/run", json={"type": "breakout", "params": {"lookback": 20, "exit_lookback": 10}, **body})
    assert response.status_code == 200, response.text
    return response.json()


def row(result, symbol):
    return next(r for r in result["rows"] if r["symbol"] == symbol)


def test_the_scan_finds_todays_buy_and_sell_and_the_trade_already_open(client, stocks):
    result = scan(client)

    aaa, bbb, ccc, ddd = (row(result, s) for s in ("AAA", "BBB", "CCC", "DDD"))
    assert (aaa["signal_today"]["side"], aaa["state"]) == ("BUY", "in")
    assert (bbb["signal_today"]["side"], bbb["state"]) == ("SELL", "out")
    assert ccc["signal_today"] is None and ccc["state"] == "in"
    assert (ccc["last_signal"]["side"], ccc["last_signal"]["days_ago"]) == ("BUY", 9)
    assert (ddd["signal_today"], ddd["last_signal"], ddd["state"]) == (None, None, "none")


def test_a_signal_says_why_and_when(client, stocks):
    aaa = row(scan(client), "AAA")

    assert aaa["signal_today"]["days_ago"] == 0
    assert aaa["signal_today"]["date"] == client.get("/api/market/status").json()["date"]
    assert "20d high" in aaa["signal_today"]["headline"]
    assert aaa["signal_today"]["checks"]
    assert aaa["last_signal"] == aaa["signal_today"]  # today's signal is also the latest one


def test_the_rows_come_best_first(client, stocks):
    symbols = [r["symbol"] for r in scan(client)["rows"]]

    ours = [s for s in symbols if s in ("AAA", "BBB", "CCC", "DDD")]
    assert ours == ["AAA", "BBB", "CCC", "DDD"]  # buy today, sell today, in a trade, nothing


def test_the_summary_counts_and_labels_the_scan(client, stocks):
    result = scan(client)

    assert result["strategy"] == "Breakout 20/10"
    rows = result["rows"]
    assert result["scanned"] == len(rows) >= 4
    # The summary counts every scanned stock. That includes the simulated ones, whose days after the imported
    # stocks' start are drawn at random each run, so one of them may also signal today: compare the summary with
    # the rows themselves, and with the four scripted stocks, whose signals are known.
    signals_today = [r["signal_today"]["side"] for r in rows if r["signal_today"]]
    assert (result["buy_today"], result["sell_today"]) == (signals_today.count("BUY"), signals_today.count("SELL"))
    assert result["buy_today"] >= 1 and result["sell_today"] >= 1  # AAA breaks out today, BBB breaks down today
    assert result["in_trade"] == sum(1 for r in rows if r["state"] == "in")
    assert result["market_date"] == client.get("/api/market/status").json()["date"]


def test_each_row_has_the_price_the_change_and_what_you_hold(client, stocks, db_session):
    client.post("/api/orders/buy", json={"symbol": "AAA", "quantity": 7})

    aaa = row(scan(client), "AAA")

    assert aaa["price"] == 110.0 and aaa["held"] == 7 and aaa["name"] == "AAA Ltd" and aaa["source"] == "csv"
    assert aaa["change_pct"] == pytest.approx((110.0 / stocks["AAA"][WARM - 2] - 1) * 100)  # the breakout day against the day before
    assert row(scan(client), "DDD")["held"] == 0


def test_the_scan_only_sees_candles_the_market_clock_has_reached(client, stocks):
    # AAA has 70 more days after its breakout, none of which have happened yet
    assert row(scan(client), "AAA")["candles"] == WARM
    client.post("/api/market/advance", json={"days": 5})
    after = row(scan(client), "AAA")
    assert after["candles"] == WARM + 5
    assert after["signal_today"] is None and after["last_signal"]["days_ago"] == 5  # yesterday's news has aged


def test_a_different_strategy_gives_different_answers(client, stocks):
    breakout = row(scan(client), "AAA")
    ma = row(scan(client, type="ma_crossover", params={"fast": 3, "slow": 8}), "AAA")
    assert breakout["signal_today"] is not None
    assert ma["last_signal"] is None or ma["last_signal"]["headline"] != breakout["signal_today"]["headline"]


def test_default_parameters_are_used_when_none_are_given(client, stocks):
    result = client.post("/api/scanner/run", json={"type": "breakout"}).json()
    assert result["strategy"] == "Breakout 20/10"


def test_custom_rules_can_be_scanned(client, stocks):
    rules = {
        "entry": {"logic": "AND", "conditions": [{"left": {"indicator": "price"}, "operator": "crosses_above", "right": {"indicator": "sma", "period": 5}}]},
        "exit": {"logic": "AND", "conditions": [{"left": {"indicator": "price"}, "operator": "crosses_below", "right": {"indicator": "sma", "period": 5}}]},
    }
    response = client.post("/api/scanner/run", json={"type": "custom", "rules": rules})

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["strategy"] == "Custom strategy"
    assert row(result, "AAA")["signal_today"]["side"] == "BUY"  # the breakout day closes above its 5-day average


def test_stocks_with_too_little_history_are_listed_without_signals(client, db_session):
    ensure_seed_data(db_session)
    import_candles(db_session, "TINY", "Tiny Ltd", closes_to_candles([100.0]), source="csv", replace=False)
    db_session.commit()

    tiny = row(scan(client), "TINY")

    assert (tiny["signal_today"], tiny["last_signal"], tiny["state"], tiny["change_pct"]) == (None, None, "none", None)


# ---------- bad requests ----------


def test_an_unknown_strategy_type_is_a_400(client, stocks):
    response = client.post("/api/scanner/run", json={"type": "nonsense"})
    assert response.status_code == 400 and "Unknown strategy type" in response.json()["detail"]


def test_bad_parameters_are_a_400(client, stocks):
    response = client.post("/api/scanner/run", json={"type": "breakout", "params": {"lookback": 1}})
    assert response.status_code == 400
    response = client.post("/api/scanner/run", json={"type": "breakout", "params": {"nope": 1}})
    assert response.status_code == 400


def test_invalid_custom_rules_are_a_400(client, stocks):
    assert client.post("/api/scanner/run", json={"type": "custom", "rules": {"entry": {}}}).status_code == 400


# ---------- it only reads ----------


def test_a_scan_changes_nothing_stored(client, stocks, db_session):
    cash = client.get("/api/portfolio").json()["cash"]
    trades = len(client.get("/api/trades").json())
    date_before = client.get("/api/market/status").json()["date"]

    scan(client)

    assert client.get("/api/portfolio").json()["cash"] == cash
    assert len(client.get("/api/trades").json()) == trades
    assert db_session.query(Position).count() == 0
    assert client.get("/api/market/status").json()["date"] == date_before
