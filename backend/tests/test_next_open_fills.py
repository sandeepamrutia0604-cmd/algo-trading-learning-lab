import pytest

from backend.app.engine import indicators
from backend.app.engine.backtest import FILL_MODES, RiskConfig, run_backtest
from backend.app.engine.cost_math import CostConfig, fill_price
from backend.tests.test_backtest import ev, make_dates, make_defn


def run(events, closes, opens, mode="next_open", capital=100_000, quantity=10, **kwargs):
    return run_backtest(
        make_defn(events), {}, make_dates(len(closes)), closes, quantity, capital,
        fill_mode=mode, opens=opens, **kwargs,
    )


CLOSES = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
OPENS = [99.5, 100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5]


# ---------- when a decision is carried out ----------


def test_the_default_mode_still_trades_at_the_close_of_the_signal_day():
    result = run_backtest(make_defn([ev(2, "BUY"), ev(5, "SELL")]), {}, make_dates(8), CLOSES, 10, 100_000)

    trade = result.trades[0]
    assert (trade.entry_date, trade.entry_price) == (make_dates(8)[2], 102.0)
    assert (trade.exit_date, trade.exit_price) == (make_dates(8)[5], 105.0)
    assert result.fill_mode == "signal_close" and result.unfilled_signal is False


def test_next_open_carries_a_signal_out_at_the_next_days_opening_price():
    result = run([ev(2, "BUY"), ev(5, "SELL")], CLOSES, OPENS)

    dates = make_dates(8)
    trade = result.trades[0]
    assert (trade.entry_date, trade.entry_price) == (dates[3], OPENS[3])  # decided at day 2's close, filled day 3's open
    assert (trade.exit_date, trade.exit_price) == (dates[6], OPENS[6])
    assert trade.pnl == pytest.approx((OPENS[6] - OPENS[3]) * 10)
    assert result.fill_mode == "next_open"


def test_a_signal_is_never_filled_at_its_own_days_open_or_close():
    result = run([ev(2, "BUY"), ev(5, "SELL")], CLOSES, OPENS)

    assert result.trades[0].entry_date > make_dates(8)[2] and result.trades[0].exit_date > make_dates(8)[5]


def test_an_overnight_gap_against_you_costs_you_in_next_open_mode_only():
    closes = [100.0] * 8
    opens = [100.0, 100.0, 100.0, 104.0, 100.0, 100.0, 100.0, 100.0]  # gaps up the morning after the signal
    events = [ev(2, "BUY"), ev(5, "SELL")]

    signal_close = run(events, closes, opens, mode="signal_close")
    next_open = run(events, closes, opens, mode="next_open")

    assert signal_close.final_capital == 100_000  # bought and sold at 100
    assert next_open.final_capital == pytest.approx(100_000 - 4 * 10 + (100 - 100) * 10 - 0)  # paid 104 for what closes at 100
    assert next_open.trades[0].entry_price == 104.0


def test_the_account_is_still_marked_to_market_at_each_close():
    result = run([ev(2, "BUY")], CLOSES, OPENS)

    curve = {p.date: p.value for p in result.equity_curve}
    dates = make_dates(8)
    cash = 100_000 - OPENS[3] * 10
    assert curve[dates[2]] == 100_000  # nothing held yet on the signal day
    assert curve[dates[3]] == pytest.approx(cash + CLOSES[3] * 10)  # bought at the open, valued at the close
    assert curve[dates[7]] == pytest.approx(cash + CLOSES[7] * 10)


# ---------- the end of the data ----------


def test_a_buy_signal_on_the_last_day_has_no_next_day_and_is_dropped():
    result = run([ev(7, "BUY")], CLOSES, OPENS)

    assert result.trades == [] and result.unfilled_signal is True
    assert result.final_capital == 100_000


def test_a_sell_signal_on_the_last_day_leaves_the_position_open():
    result = run([ev(2, "BUY"), ev(7, "SELL")], CLOSES, OPENS)

    assert result.trades[0].is_open and result.unfilled_signal is True


def test_nothing_is_flagged_when_every_decision_found_a_next_day():
    assert run([ev(2, "BUY"), ev(5, "SELL")], CLOSES, OPENS).unfilled_signal is False


# ---------- inputs ----------


def test_next_open_needs_one_opening_price_per_close():
    for bad in (None, [100.0], OPENS + [1.0]):
        with pytest.raises(ValueError, match="opening price"):
            run([ev(2, "BUY")], CLOSES, bad)


def test_an_unknown_fill_mode_is_refused():
    with pytest.raises(ValueError, match="Unknown fill mode"):
        run([ev(2, "BUY")], CLOSES, OPENS, mode="whenever")
    assert FILL_MODES == ("signal_close", "next_open")


def test_the_signal_close_mode_ignores_opens_entirely():
    with_opens = run([ev(2, "BUY"), ev(5, "SELL")], CLOSES, OPENS, mode="signal_close")
    without = run([ev(2, "BUY"), ev(5, "SELL")], CLOSES, None, mode="signal_close")

    assert with_opens.final_capital == without.final_capital and with_opens.trades[0].entry_price == 102.0


# ---------- sizing, cash, costs ----------


def test_cash_is_checked_at_the_open_so_a_gap_can_make_the_buy_unaffordable():
    closes = [100.0] * 6
    opens = [100.0, 100.0, 100.0, 110.0, 100.0, 100.0]  # gaps up after the signal

    next_open = run([ev(2, "BUY")], closes, opens, capital=1_005)  # 10 shares fit at 100, not at 110
    signal_close = run([ev(2, "BUY")], closes, opens, mode="signal_close", capital=1_005)

    assert next_open.trades == [] and next_open.skipped_buys == 1
    assert signal_close.trades[0].quantity == 10


def test_a_risk_sized_buy_is_sized_from_the_signal_days_close():
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2.0, stop_loss_pct=5.0, max_allocation_pct=100.0)
    closes = [100.0] * 6
    opens = [100.0, 100.0, 100.0, 103.0, 100.0, 100.0]

    result = run([ev(2, "BUY")], closes, opens, capital=1_000_000, risk=risk)

    assert result.trades[0].quantity == 4000  # 2% of 10,00,000 over a 5-rupee stop at the close of 100, not 103
    assert result.trades[0].entry_price == 103.0


def test_the_allocation_cap_is_checked_at_the_price_actually_paid():
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2.0, stop_loss_pct=5.0, max_allocation_pct=20.0)
    closes = [100.0] * 6
    opens = [100.0, 100.0, 100.0, 101.0, 100.0, 100.0]  # sized to exactly 20% at 100; 2,02,000 at 101 is over the cap

    result = run([ev(2, "BUY")], closes, opens, capital=1_000_000, risk=risk)

    assert result.trades == [] and result.skipped_buys == 1


def test_costs_apply_to_the_opening_fill():
    costs = CostConfig(enabled=True, slippage_pct=1.0, brokerage_pct=0.0, brokerage_cap=0.0, other_charges_pct=0.0)

    result = run([ev(2, "BUY"), ev(5, "SELL")], CLOSES, OPENS, costs=costs)

    trade = result.trades[0]
    assert trade.entry_price == fill_price(OPENS[3], "BUY", costs) and trade.entry_price > OPENS[3]
    assert trade.exit_price == fill_price(OPENS[6], "SELL", costs) and trade.exit_price < OPENS[6]
    assert result.slippage_cost == pytest.approx(((trade.entry_price - OPENS[3]) + (OPENS[6] - trade.exit_price)) * 10)


# ---------- stops ----------


def test_a_stop_loss_is_noticed_at_the_close_and_carried_out_at_the_next_open():
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2.0, stop_loss_pct=5.0, max_allocation_pct=100.0)
    closes = [100.0, 100.0, 100.0, 100.0, 94.0, 94.0, 94.0, 94.0]  # day 4 closes through the 95 stop
    opens = [100.0, 100.0, 100.0, 100.0, 99.0, 93.0, 94.0, 94.0]

    result = run([ev(2, "BUY")], closes, opens, capital=1_000_000, risk=risk)

    trade = result.trades[0]
    assert trade.stopped_out and result.stopped_out == 1
    assert trade.exit_date == make_dates(8)[5] and trade.exit_price == 93.0  # the next open, which can be worse than the stop


def test_a_stop_triggered_on_the_last_day_cannot_be_carried_out():
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2.0, stop_loss_pct=5.0, max_allocation_pct=100.0)
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 94.0]
    opens = [100.0] * 8

    result = run([ev(2, "BUY")], closes, opens, capital=1_000_000, risk=risk)

    assert result.trades[0].is_open and result.stopped_out == 0 and result.unfilled_signal is True


def test_the_stop_distance_is_the_volatility_known_on_the_signal_day():
    closes = [100, 101, 99.5, 101.2, 100.1, 102.0, 100.4, 101.9, 100.2, 102.5, 100.9, 103.0, 101.1, 102.7, 101.0]
    opens = list(closes)
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2.0, stop_loss_pct=5.0, max_allocation_pct=100.0,
                      stop_mode="volatility", volatility_window=5, volatility_multiplier=2.0)
    signal = 10

    result = run([ev(signal, "BUY")], closes, opens, capital=1_000_000, risk=risk)

    expected = 2.0 * indicators.volatility_pct(closes, 5)[signal]
    assert result.trades[0].stop_pct == pytest.approx(expected)
    assert result.trades[0].entry_date == make_dates(len(closes))[signal + 1]


# ---------- no look-ahead ----------


def test_whether_a_trade_happens_does_not_depend_on_the_next_days_open():
    low = run([ev(2, "BUY"), ev(5, "SELL")], CLOSES, [o - 5 for o in OPENS])
    high = run([ev(2, "BUY"), ev(5, "SELL")], CLOSES, [o + 5 for o in OPENS])

    assert len(low.trades) == len(high.trades) == 1
    assert (low.trades[0].entry_date, low.trades[0].exit_date) == (high.trades[0].entry_date, high.trades[0].exit_date)
    assert low.trades[0].entry_price != high.trades[0].entry_price  # only the price paid differs


def test_signals_before_the_traded_window_are_not_carried_out_into_it():
    result = run([ev(3, "BUY"), ev(6, "SELL")], CLOSES, OPENS, start_index=4)

    assert result.trades == []  # the BUY was decided before the window began
    assert result.equity_curve[0].date == make_dates(8)[4]


def test_the_close_and_open_modes_agree_when_the_open_equals_the_previous_close():
    # no overnight gap and a signal one day earlier: next-open on day i+1 is the same price as the close on day i
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
    opens = [100.0] + closes[:-1]

    close_mode = run([ev(2, "BUY"), ev(5, "SELL")], closes, opens, mode="signal_close")
    open_mode = run([ev(2, "BUY"), ev(5, "SELL")], closes, opens, mode="next_open")

    assert close_mode.trades[0].entry_price == open_mode.trades[0].entry_price == 102.0
    assert close_mode.final_capital == pytest.approx(open_mode.final_capital)
    assert open_mode.trades[0].entry_date > close_mode.trades[0].entry_date  # just a day later


# ---------- through the API ----------


@pytest.fixture()
def market(client):
    client.post("/api/market/generate", json={"days": 400, "seed": 11})
    return {p["date"]: p for p in client.get("/api/stocks/ALPHA/prices?full=true").json()}


RUN = {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 3, "slow": 8}, "quantity": 10, "initial_capital": 100_000}


def api_run(client, **change):
    return client.post("/api/backtests/run", json={**RUN, **change})


def test_the_default_is_the_signal_close_and_unchanged(client, market):
    plain = api_run(client).json()
    explicit = api_run(client, fill_mode="signal_close").json()

    assert plain == explicit and plain["fill_mode"] == "signal_close" and plain["unfilled_signal"] is False


def test_next_open_trades_happen_at_the_actual_opening_prices(client, market):
    result = api_run(client, fill_mode="next_open").json()

    assert result["fill_mode"] == "next_open" and result["trades"]
    for trade in result["trades"]:
        assert trade["entry_price"] == pytest.approx(market[trade["entry_date"]]["open"])
        if not trade["open"]:
            assert trade["exit_price"] == pytest.approx(market[trade["exit_date"]]["open"])


def test_every_next_open_entry_is_the_trading_day_after_a_signal_close_entry(client, market):
    close_trades = api_run(client).json()["trades"]
    open_trades = api_run(client, fill_mode="next_open").json()["trades"]
    days = sorted(market)

    expected = {days[days.index(t["entry_date"]) + 1] for t in close_trades if t["entry_date"] != days[-1]}
    assert open_trades and {t["entry_date"] for t in open_trades} == expected  # same signals, one day later


def test_an_unknown_fill_mode_is_rejected(client, market):
    assert api_run(client, fill_mode="whenever").status_code == 422


def test_the_optimiser_and_walk_forward_accept_it_and_say_so(client, market):
    base = {"symbol": "ALPHA", "type": "ma_crossover", "x": {"param": "fast", "low": 3, "high": 7, "step": 2}, "y": {"param": "slow", "low": 10, "high": 20, "step": 5}, "quantity": 10, "initial_capital": 100_000}

    plain = client.post("/api/backtests/optimise", json=base).json()
    opened = client.post("/api/backtests/optimise", json={**base, "fill_mode": "next_open"}).json()
    walk = client.post("/api/backtests/walk-forward", json={**base, "fill_mode": "next_open", "folds": 3}).json()

    assert (plain["fill_mode"], opened["fill_mode"], walk["fill_mode"]) == ("signal_close", "next_open", "next_open")
    assert plain["train"]["cells"] != opened["train"]["cells"]
    assert client.post("/api/backtests/optimise", json={**base, "fill_mode": "whenever"}).status_code == 422


def test_an_optimiser_cell_equals_the_same_backtest_with_next_open_fills(client, market):
    base = {"symbol": "ALPHA", "type": "ma_crossover", "x": {"param": "fast", "low": 3, "high": 7, "step": 2}, "y": {"param": "slow", "low": 10, "high": 20, "step": 5}, "quantity": 10, "initial_capital": 100_000, "fill_mode": "next_open"}
    days = sorted(market)

    result = client.post("/api/backtests/optimise", json={**base, "train_start": days[0], "train_end": days[299], "test_start": days[300], "test_end": days[-1]}).json()
    run = api_run(client, params=result["best"]["params"], fill_mode="next_open", start_date=days[0], end_date=days[299]).json()

    assert result["best"]["train"]["return_pct"] == pytest.approx(run["total_return_pct"], abs=1e-3)
    assert result["best"]["train"]["trades"] == run["total_trades"]


def test_monte_carlo_follows_the_fill_mode(client, market):
    request = {"request": {**RUN, "fill_mode": "next_open"}, "simulations": 200, "method": "shuffle", "seed": 1}

    result = client.post("/api/backtests/monte-carlo", json=request).json()
    default = client.post("/api/backtests/monte-carlo", json={**request, "request": RUN}).json()

    assert result["fill_mode"] == "next_open" and default["fill_mode"] == "signal_close"
    assert result["original"] != default["original"]


def test_a_saved_backtest_remembers_the_fill_mode_and_says_so_in_its_name(client, market):
    saved = client.post("/api/backtests/saved", json={"request": {**RUN, "fill_mode": "next_open"}}).json()
    plain = client.post("/api/backtests/saved", json={"request": RUN}).json()

    detail = client.get(f"/api/backtests/saved/{saved['id']}").json()
    assert detail["request"]["fill_mode"] == "next_open" and detail["result"]["fill_mode"] == "next_open"
    assert saved["name"].endswith("next-open fills") and "next-open" not in plain["name"]
