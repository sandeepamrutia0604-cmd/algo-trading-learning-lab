"""Order-level stop-loss and take-profit in backtests: the same rules a live order uses (engine/exit_math.py),
checked every day against that day's open, high and low."""

import pytest

from backend.app.engine.backtest import ExitConfig, RiskConfig, run_backtest
from backend.app.engine.cost_math import CostConfig
from backend.app.services import backtest_service
from backend.app.services.exceptions import InvalidStrategyError
from backend.tests.test_backtest import ev, make_dates, make_defn
from backend.tests.test_exit_orders import QUIET, WARM, advance, buy, market, position, trades  # noqa: F401  (market is a fixture)

FLAT = (100.0, 100.5, 99.5, 100.0)  # open, high, low, close of a quiet day


def series(rows):
    opens, highs, lows, closes = ([row[i] for row in rows] for i in range(4))
    return opens, highs, lows, closes


def run(events, rows, exits=None, mode="signal_close", capital=100_000, quantity=10, **kwargs):
    opens, highs, lows, closes = series(rows)
    return run_backtest(
        make_defn(events), {}, make_dates(len(rows)), closes, quantity, capital,
        fill_mode=mode, opens=opens, highs=highs, lows=lows, exits=exits, **kwargs,
    )


def with_days(**days):
    """Eight quiet days with some replaced: with_days(d3=(open, high, low, close))."""
    rows = [FLAT] * 8
    for key, row in days.items():
        rows[int(key[1:])] = row
    return rows


BUY_DAY_1 = [ev(1, "BUY")]  # bought at day 1's close, 100


# ---------- the levels ----------


def test_levels_come_from_the_entry_price_and_are_rounded_like_the_order_ticket():
    assert ExitConfig(5, 10).levels(100.0) == (95.0, 110.0)
    assert ExitConfig(5, 10).levels(100.333) == (95.32, 110.37)
    assert ExitConfig(stop_pct=5).levels(200.0) == (190.0, None)
    assert ExitConfig(target_pct=2).levels(200.0) == (None, 204.0)
    assert ExitConfig().levels(100.0) == (None, None) and not ExitConfig().enabled


def test_rounding_never_puts_a_level_on_the_wrong_side_of_the_entry():
    stop, target = ExitConfig(0.1, 0.1).levels(0.5)  # 0.4995 and 0.5005 would round onto the entry
    assert stop < 0.5 < target


# ---------- a stop-loss ----------


def test_a_stop_is_hit_when_the_days_low_reaches_it_and_fills_at_the_level():
    result = run(BUY_DAY_1, with_days(d3=(99.0, 101.0, 94.0, 96.0)), ExitConfig(stop_pct=5))

    trade = result.trades[0]
    assert (trade.exit_date, trade.exit_price) == (make_dates(8)[3], 95.0)
    assert trade.exit_reason == "stop_loss" and trade.stopped_out is True
    assert trade.pnl == pytest.approx(-50.0)
    assert (result.stopped_out, result.take_profits) == (1, 0)
    assert (result.stop_loss_pct, result.take_profit_pct) == (5, None)


def test_a_day_that_opens_below_the_stop_fills_at_the_open_not_the_level():
    result = run(BUY_DAY_1, with_days(d3=(90.0, 92.0, 88.0, 91.0)), ExitConfig(stop_pct=5))

    assert result.trades[0].exit_price == 90.0  # the gap: 95 was never available
    assert result.trades[0].pnl == pytest.approx(-100.0)


def test_a_low_that_stays_above_the_stop_does_not_trigger_it():
    result = run(BUY_DAY_1, with_days(d3=(99.0, 101.0, 95.01, 97.0)), ExitConfig(stop_pct=5))
    assert result.trades[0].is_open


# ---------- a take-profit ----------


def test_a_target_is_hit_when_the_days_high_reaches_it_and_fills_at_the_level():
    result = run(BUY_DAY_1, with_days(d4=(101.0, 112.0, 100.0, 108.0)), ExitConfig(target_pct=10))

    trade = result.trades[0]
    assert (trade.exit_date, trade.exit_price) == (make_dates(8)[4], 110.0)
    assert trade.exit_reason == "take_profit" and trade.stopped_out is False
    assert trade.pnl == pytest.approx(100.0)
    assert (result.stopped_out, result.take_profits) == (0, 1)


def test_a_day_that_opens_above_the_target_fills_at_the_open():
    result = run(BUY_DAY_1, with_days(d4=(115.0, 118.0, 114.0, 116.0)), ExitConfig(target_pct=10))
    assert result.trades[0].exit_price == 115.0


# ---------- both levels ----------


def test_a_day_that_reaches_both_levels_takes_the_stop():
    result = run(BUY_DAY_1, with_days(d3=(100.0, 112.0, 94.0, 100.0)), ExitConfig(stop_pct=5, target_pct=10))

    assert result.trades[0].exit_price == 95.0 and result.trades[0].exit_reason == "stop_loss"


def test_whichever_level_is_reached_first_wins_across_days():
    rows = with_days(d3=(100.0, 112.0, 99.0, 108.0), d5=(100.0, 101.0, 90.0, 92.0))
    result = run(BUY_DAY_1, rows, ExitConfig(stop_pct=5, target_pct=10))
    assert (result.trades[0].exit_reason, result.trades[0].exit_date) == ("take_profit", make_dates(8)[3])


# ---------- when checking starts ----------


def test_a_trade_entered_at_a_close_is_first_checked_the_next_day():
    # day 1's own range dips below the stop, but the trade only exists from day 1's close
    rows = with_days(d1=(100.0, 101.0, 90.0, 100.0))
    result = run(BUY_DAY_1, rows, ExitConfig(stop_pct=5))
    assert result.trades[0].is_open


def test_a_trade_entered_at_an_open_is_protected_from_that_same_day():
    # decided at day 1's close, filled at day 2's open (100), and day 2 then trades down to 90
    rows = with_days(d2=(100.0, 101.0, 90.0, 92.0))
    result = run(BUY_DAY_1, rows, ExitConfig(stop_pct=5), mode="next_open")

    trade = result.trades[0]
    assert trade.entry_date == trade.exit_date == make_dates(8)[2]
    assert (trade.entry_price, trade.exit_price, trade.exit_reason) == (100.0, 95.0, "stop_loss")


# ---------- costs ----------


def test_slippage_and_charges_apply_to_the_exit_like_any_other_sale():
    costs = CostConfig(enabled=True, slippage_pct=1.0, brokerage_pct=0.1, other_charges_pct=0.0)
    result = run(BUY_DAY_1, with_days(d3=(99.0, 101.0, 90.0, 92.0)), ExitConfig(stop_pct=5), costs=costs)

    trade = result.trades[0]
    entry = 100.0 * 1.01  # slipped against the buyer
    stop = round(entry * 0.95, 2)
    assert trade.entry_price == pytest.approx(entry)
    assert trade.exit_price == round(stop * 0.99, 2)  # slipped against the seller (prices are whole paise)
    assert trade.exit_fees > 0 and result.total_fees > 0


# ---------- with the Risk management stop, and strategy signals ----------


RISK = RiskConfig(enabled=True, max_risk_per_trade_pct=1.0, stop_loss_pct=10.0, max_allocation_pct=100.0)


def test_the_order_stop_fires_first_when_the_day_reaches_it_before_the_close_stop():
    # low 94 trips the 5% order stop; the close (96) is still above the 10% risk stop at 90
    result = run(BUY_DAY_1, with_days(d3=(99.0, 100.0, 94.0, 96.0)), ExitConfig(stop_pct=5), risk=RISK)

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "stop_loss" and result.stopped_out == 1


def test_the_close_stop_still_works_when_the_order_stop_is_looser():
    # a close of 85 trips the 10% risk stop; the order stop is 40% away and is not reached
    result = run(BUY_DAY_1, with_days(d3=(99.0, 100.0, 84.0, 85.0)), ExitConfig(stop_pct=40), risk=RISK)

    assert result.trades[0].exit_reason == "risk_stop" and result.stopped_out == 1


def test_a_buy_signal_the_same_day_a_stop_fires_still_buys_again():
    events = [ev(1, "BUY"), ev(3, "BUY")]
    result = run(events, with_days(d3=(99.0, 100.0, 94.0, 96.0)), ExitConfig(stop_pct=5))

    assert len(result.trades) == 2
    assert result.trades[0].exit_date == result.trades[1].entry_date == make_dates(8)[3]  # sold in the morning, bought at the close
    assert result.trades[1].is_open


def test_a_sell_signal_after_the_exit_has_nothing_left_to_sell():
    events = [ev(1, "BUY"), ev(3, "SELL")]
    result = run(events, with_days(d3=(99.0, 100.0, 94.0, 96.0)), ExitConfig(stop_pct=5))
    assert len(result.trades) == 1 and result.trades[0].exit_reason == "stop_loss"  # the stop got there first


def test_an_ordinary_signal_exit_is_labelled_a_signal():
    result = run([ev(1, "BUY"), ev(4, "SELL")], with_days(), ExitConfig(stop_pct=5, target_pct=10))
    assert result.trades[0].exit_reason == "signal" and result.trades[0].stopped_out is False


# ---------- off means off ----------


def test_without_exits_every_result_is_exactly_what_it_was():
    rows = with_days(d3=(99.0, 101.0, 90.0, 92.0), d5=(100.0, 120.0, 100.0, 118.0))
    events = [ev(1, "BUY"), ev(6, "SELL")]
    opens, highs, lows, closes = series(rows)

    plain = run_backtest(make_defn(events), {}, make_dates(8), closes, 10, 100_000)
    with_data = run(events, rows)  # candle data supplied, but no exits asked for
    empty = run(events, rows, ExitConfig())

    for other in (with_data, empty):
        assert other.final_capital == plain.final_capital
        assert [(t.entry_date, t.exit_date, t.exit_price) for t in other.trades] == [(t.entry_date, t.exit_date, t.exit_price) for t in plain.trades]
    assert plain.trades[0].exit_reason == "signal" and plain.take_profits == 0


def test_exits_without_candle_data_are_refused():
    closes = [100.0] * 8
    with pytest.raises(ValueError, match="open, high and low"):
        run_backtest(make_defn(BUY_DAY_1), {}, make_dates(8), closes, 10, 100_000, exits=ExitConfig(stop_pct=5))
    with pytest.raises(ValueError, match="open, high and low"):
        run_backtest(make_defn(BUY_DAY_1), {}, make_dates(8), closes, 10, 100_000, exits=ExitConfig(5), opens=closes, highs=closes[:-1], lows=closes)


# ---------- the same rules as a live order ----------


def test_a_backtest_and_a_live_position_exit_on_the_same_day_at_the_same_price(client, market, db_session):  # noqa: F811
    script = {3: (100.0, 102.0, 93.0, 96.0)}  # day 3 trades down through a 5% stop
    candles = market(script)
    buy(client, quantity=10, stop_loss_price=95.0, take_profit_price=110.0)
    advance(client, 3)

    live = trades(client)
    assert len(live) == 2 and live[0]["side"] == "SELL"  # newest first
    live_exit = live[0]

    closes = [c.close for c in candles]
    result = run_backtest(
        make_defn([ev(WARM - 1, "BUY")]), {}, [c.date for c in candles], closes, 10, 100_000,
        start_index=WARM - 1, opens=[c.open for c in candles], highs=[c.high for c in candles], lows=[c.low for c in candles],
        exits=ExitConfig(stop_pct=5, target_pct=10),
    )

    trade = result.trades[0]
    assert str(trade.exit_date) == live_exit["market_date"]
    assert trade.exit_price == pytest.approx(live_exit["price"]) == pytest.approx(95.0)
    assert trade.entry_price == pytest.approx(live[1]["price"])


def test_a_backtest_and_a_live_target_agree_too(client, market):  # noqa: F811
    script = {2: (101.0, 112.0, 100.0, 108.0)}
    candles = market(script)
    buy(client, quantity=10, stop_loss_price=95.0, take_profit_price=110.0)
    advance(client, 2)

    live_exit = trades(client)[0]
    result = run_backtest(
        make_defn([ev(WARM - 1, "BUY")]), {}, [c.date for c in candles], [c.close for c in candles], 10, 100_000,
        start_index=WARM - 1, opens=[c.open for c in candles], highs=[c.high for c in candles], lows=[c.low for c in candles],
        exits=ExitConfig(stop_pct=5, target_pct=10),
    )

    trade = result.trades[0]
    assert str(trade.exit_date) == live_exit["market_date"]
    assert trade.exit_price == pytest.approx(live_exit["price"]) == pytest.approx(110.0)
    assert trade.exit_reason == "take_profit"


# ---------- the service and the API ----------


def test_the_service_refuses_nonsense_levels():
    for stop, target in [(0, None), (100, None), (-1, None), (None, 0), (None, -5), (None, 1001)]:
        with pytest.raises(InvalidStrategyError):
            backtest_service.exit_config(stop, target)
    assert backtest_service.exit_config(None, None) == ExitConfig()
    assert backtest_service.exit_config(5, 10) == ExitConfig(5, 10)


def history(client):
    client.post("/api/market/generate", json={"days": 220, "seed": 3})


def request(**extra):
    return {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 5, "slow": 20}, "quantity": 10, "initial_capital": 100_000, **extra}


def test_the_api_rejects_out_of_range_levels(client):
    history(client)
    for extra in ({"stop_loss_pct": 0}, {"stop_loss_pct": 100}, {"stop_loss_pct": -3}, {"take_profit_pct": 0}, {"take_profit_pct": 5000}):
        assert client.post("/api/backtests/run", json=request(**extra)).status_code == 422


def test_a_run_with_levels_reports_why_each_trade_closed_and_echoes_the_levels(client):
    history(client)
    plain = client.post("/api/backtests/run", json=request()).json()
    tight = client.post("/api/backtests/run", json=request(stop_loss_pct=1, take_profit_pct=1)).json()

    assert plain["stop_loss_pct"] is None and plain["take_profit_pct"] is None and plain["take_profits"] == 0
    assert (tight["stop_loss_pct"], tight["take_profit_pct"]) == (1, 1)
    reasons = {t["exit_reason"] for t in tight["trades"] if not t["open"]}
    assert reasons and reasons <= {"signal", "risk_stop", "stop_loss", "take_profit"}
    assert reasons & {"stop_loss", "take_profit"}  # 1% levels on a 220-day series are certainly reached
    assert tight["take_profits"] == sum(1 for t in tight["trades"] if t["exit_reason"] == "take_profit")
    assert tight["final_capital"] != plain["final_capital"]  # the exits really changed what happened


def test_a_saved_run_with_levels_round_trips_and_is_named_after_them(client):
    history(client)
    saved = client.post("/api/backtests/saved", json={"request": request(stop_loss_pct=5, take_profit_pct=10)}).json()

    assert saved["name"].endswith(", 5% stop / 10% target")
    detail = client.get(f"/api/backtests/saved/{saved['id']}").json()
    assert (detail["request"]["stop_loss_pct"], detail["request"]["take_profit_pct"]) == (5, 10)
    assert (detail["result"]["stop_loss_pct"], detail["result"]["take_profit_pct"]) == (5, 10)


def test_a_run_saved_before_levels_existed_still_loads(client, db_session):
    from backend.app.models import SavedBacktest

    history(client)
    saved = client.post("/api/backtests/saved", json={"request": request()}).json()
    row = db_session.get(SavedBacktest, saved["id"])
    old_request, old_result = dict(row.request), dict(row.result)
    for key in ("stop_loss_pct", "take_profit_pct"):
        old_request.pop(key, None)
        old_result.pop(key, None)
    old_result.pop("take_profits", None)
    old_result["trades"] = [{k: v for k, v in t.items() if k != "exit_reason"} for t in old_result["trades"]]
    row.request, row.result = old_request, old_result
    db_session.commit()

    detail = client.get(f"/api/backtests/saved/{saved['id']}")

    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["request"]["stop_loss_pct"] is None and body["result"]["take_profits"] == 0
    assert all(t["exit_reason"] is None for t in body["result"]["trades"])


def test_monte_carlo_runs_the_backtest_with_the_levels(client):
    history(client)
    response = client.post(
        "/api/backtests/monte-carlo", json={"request": request(stop_loss_pct=1, take_profit_pct=1), "simulations": 500, "method": "bootstrap"}
    )
    assert response.status_code == 200, response.text
    assert (response.json()["stop_loss_pct"], response.json()["take_profit_pct"]) == (1, 1)


OPTIMISE = {
    "symbol": "ALPHA", "type": "ma_crossover", "params": {}, "quantity": 10, "initial_capital": 100_000,
    "x": {"param": "fast", "low": 5, "high": 9, "step": 2}, "y": {"param": "slow", "low": 20, "high": 30, "step": 10},
    "train_end": None,
}


def test_the_optimiser_holds_the_levels_fixed_while_it_sweeps(client):
    history(client)
    plain = client.post("/api/backtests/optimise", json=OPTIMISE).json()
    levelled = client.post("/api/backtests/optimise", json={**OPTIMISE, "stop_loss_pct": 1, "take_profit_pct": 1})

    assert levelled.status_code == 200, levelled.text
    body = levelled.json()
    assert (body["stop_loss_pct"], body["take_profit_pct"]) == (1, 1) and plain["stop_loss_pct"] is None
    assert body["train"]["cells"] != plain["train"]["cells"]  # the same grid scores differently with exits on


def test_walk_forward_passes_the_levels_through(client):
    history(client)
    body = {**OPTIMISE, "folds": 3, "train_ratio": 2.0, "mode": "rolling", "stop_loss_pct": 2, "take_profit_pct": 4}
    body.pop("train_end")
    response = client.post("/api/backtests/walk-forward", json=body)

    assert response.status_code == 200, response.text
    assert (response.json()["stop_loss_pct"], response.json()["take_profit_pct"]) == (2, 4)
