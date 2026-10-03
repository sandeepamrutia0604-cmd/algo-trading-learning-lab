from datetime import date

import pytest

from backend.app.engine.backtest import RiskConfig, run_backtest
from backend.app.services import backtest_service, risk_service
from backend.app.services.exceptions import InvalidStrategyError
from backend.app.strategies.base import SignalEvent, StrategyDef
from backend.app.strategies.registry import list_definitions

ALL = [d.key for d in list_definitions()]


def make_defn(events):
    """A stub StrategyDef whose generate() returns a fixed set of signals, so the backtest
    engine itself can be tested without depending on any real indicator's math."""
    return StrategyDef(
        key="stub",
        label="Stub",
        summary="",
        works_best="",
        struggles="",
        params=(),
        entry_text="",
        exit_text="",
        generate=lambda closes, params: events,
        chart_series=lambda closes, params: [],
        name_fn=lambda params: "Stub",
    )


def ev(index, side):
    return SignalEvent(index=index, side=side, headline="", checks=[], values={})


def make_dates(n):
    return [date(2025, 1, 1 + i) for i in range(n)]


# ---------- pure engine ----------


def test_backtest_replays_a_win_then_leaves_a_trade_open():
    closes = [100, 100, 110, 90, 90, 120, 120]
    dates = make_dates(len(closes))
    events = [
        SignalEvent(index=1, side="BUY", headline="", checks=[], values={}),
        SignalEvent(index=3, side="SELL", headline="", checks=[], values={}),
        SignalEvent(index=5, side="BUY", headline="", checks=[], values={}),
    ]
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=10_000)

    assert len(result.trades) == 2
    closed, open_trade = result.trades
    assert (closed.entry_price, closed.exit_price, closed.pnl) == (100, 90, -100)
    assert closed.pnl_pct == pytest.approx(-10.0)
    assert open_trade.is_open and open_trade.entry_price == 120

    assert result.total_trades == 1  # only the closed round-trip counts
    assert (result.winning_trades, result.losing_trades) == (0, 1)
    assert result.win_rate_pct == 0.0
    assert result.final_capital == pytest.approx(9900.0)
    assert result.total_return_pct == pytest.approx(-1.0)
    assert result.max_drawdown_pct == pytest.approx((10100 - 9900) / 10100 * 100)
    assert result.skipped_buys == 0
    assert [p.value for p in result.equity_curve] == pytest.approx([10000, 10000, 10100, 9900, 9900, 9900, 9900])


def test_backtest_skips_a_buy_it_cannot_afford_and_stays_flat():
    closes = [100, 100, 110, 90, 90, 120, 120]
    dates = make_dates(len(closes))
    events = [
        SignalEvent(index=1, side="BUY", headline="", checks=[], values={}),
        SignalEvent(index=3, side="SELL", headline="", checks=[], values={}),
        SignalEvent(index=5, side="BUY", headline="", checks=[], values={}),
    ]
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=500)

    assert result.trades == []
    assert result.skipped_buys == 2
    assert result.total_trades == 0
    assert result.win_rate_pct == 0.0
    assert result.final_capital == 500
    assert result.total_return_pct == 0.0
    assert result.max_drawdown_pct == 0.0
    assert all(p.value == 500 for p in result.equity_curve)


def test_backtest_with_no_signals_holds_cash_flat():
    closes = [50, 51, 49, 52]
    dates = make_dates(len(closes))
    result = run_backtest(make_defn([]), {}, dates, closes, quantity=5, initial_capital=1000)

    assert result.trades == []
    assert result.total_trades == 0
    assert result.final_capital == 1000
    assert result.total_return_pct == 0.0
    assert len(result.equity_curve) == len(closes)


def test_a_leading_sell_signal_is_ignored_because_nothing_is_held():
    closes = [100, 90]
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="SELL", headline="", checks=[], values={})]
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=1, initial_capital=1000)

    assert result.trades == []
    assert result.final_capital == 1000


# ---------- risk management ----------


def test_risk_managed_backtest_sizes_buys_from_the_risk_formula():
    # Capital 1,00,000, Risk 2% -> 2,000 max risk; Entry 100 / 5% stop -> 5 risk/share -> 400 shares
    closes = [100, 100]
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=100)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=100_000, risk=risk)

    assert result.trades[0].quantity == 400  # not the fixed quantity=10


def test_risk_disabled_keeps_the_fixed_quantity_even_with_risk_fields_set():
    closes = [100, 100]
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=False, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=10)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=100_000, risk=risk)

    assert result.trades[0].quantity == 10


def test_risk_managed_backtest_stop_loss_force_exits_without_a_strategy_sell_signal():
    closes = [100, 100, 94]  # 5% stop from entry 100 is 95; day 2 closes at 94
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=True, stop_loss_pct=5)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=100_000, risk=risk)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.stopped_out is True
    assert (trade.exit_date, trade.exit_price) == (dates[2], 94)
    assert result.stopped_out == 1


def test_risk_managed_backtest_no_stop_loss_while_price_stays_above_the_stop():
    closes = [100, 100, 96]  # above the 95 stop
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=True, stop_loss_pct=5)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=100_000, risk=risk)

    assert result.trades[0].is_open
    assert result.stopped_out == 0


def test_risk_managed_backtest_shrinks_a_risk_sized_buy_to_the_allocation_cap():
    # The risk formula wants 1,000 shares (all 1,00,000 cash, 100% allocation); the cap is 50%.
    closes = [100, 100]
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=5, stop_loss_pct=5, max_allocation_pct=50)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=100_000, risk=risk)

    assert result.trades[0].quantity == 500
    assert result.skipped_buys == 0


def test_the_default_risk_settings_no_longer_skip_every_buy():
    # 2% risk / 5% stop wants 40% of equity; the default 20% cap used to reject that outright.
    closes = [100, 100]
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=20)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=100_000, risk=risk)

    assert result.trades[0].quantity == 200  # 20% of 1,00,000 at 100 a share
    assert result.skipped_buys == 0


def test_a_buy_that_cannot_afford_even_one_share_under_the_cap_is_skipped():
    closes = [30_000, 30_000]  # 20% of 1,00,000 is 20,000, below one share
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=20)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=100_000, risk=risk)

    assert result.trades == []
    assert result.skipped_buys == 1


def test_a_fixed_quantity_over_the_cap_is_still_skipped_not_shrunk():
    # Risk sizing isn't configured (no stop-loss), so quantity=100 is the user's explicit choice.
    closes = [100, 100]
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=True, max_allocation_pct=5)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=100, initial_capital=100_000, risk=risk)

    assert result.trades == []
    assert result.skipped_buys == 1


# ---------- service ----------


def test_service_rejects_non_positive_quantity_or_capital(db_session):
    with pytest.raises(InvalidStrategyError, match="Quantity"):
        backtest_service.run(db_session, "ALPHA", "ma_crossover", {}, 0, 100_000)
    with pytest.raises(InvalidStrategyError, match="capital"):
        backtest_service.run(db_session, "ALPHA", "ma_crossover", {}, 10, 0)


def test_service_rejects_unknown_strategy_type(db_session):
    with pytest.raises(InvalidStrategyError):
        backtest_service.run(db_session, "ALPHA", "not-a-type", {}, 10, 100_000)


def test_service_requires_some_price_history(db_session):
    with pytest.raises(InvalidStrategyError, match="history"):
        backtest_service.run(db_session, "ALPHA", "ma_crossover", {}, 10, 100_000)


def test_service_backtest_picks_up_saved_risk_settings(client, db_session):
    client.post("/api/market/generate", json={"days": 100, "seed": 1})
    risk_service.update_settings(db_session, enabled=True, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=100)

    _, _, _, _, result, risk_managed = backtest_service.run(db_session, "ALPHA", "ma_crossover", {}, 10, 100_000)
    assert risk_managed is True
    # with risk management on, any filled trade is sized by the formula, not the fixed quantity=10
    assert all(t.quantity != 10 for t in result.trades) or not result.trades


def test_service_backtest_risk_managed_false_when_risk_settings_disabled(client, db_session):
    client.post("/api/market/generate", json={"days": 60, "seed": 1})
    _, _, _, _, _, risk_managed = backtest_service.run(db_session, "ALPHA", "ma_crossover", {}, 10, 100_000)
    assert risk_managed is False


# ---------- API ----------


@pytest.mark.parametrize("key", ALL)
def test_backtest_endpoint_runs_every_strategy_type_and_returns_consistent_metrics(client, key):
    client.post("/api/market/generate", json={"days": 250, "seed": 11})
    res = client.post(
        "/api/backtests/run",
        json={"symbol": "ALPHA", "type": key, "quantity": 10, "initial_capital": 100_000},
    )
    assert res.status_code == 200
    body = res.json()

    assert body["type"] == key
    assert len(body["equity_curve"]) == 250
    assert body["equity_curve"][-1]["value"] == pytest.approx(body["final_capital"])
    assert body["total_trades"] == body["winning_trades"] + body["losing_trades"]
    assert 0 <= body["win_rate_pct"] <= 100
    assert body["max_drawdown_pct"] >= 0
    assert body["series"] and all(s["points"] for s in body["series"])
    if key in ("rsi", "combined"):
        assert any(s["panel"] == "osc" and s["y_range"] == [0, 100] for s in body["series"])


def test_backtest_endpoint_404_for_unknown_symbol(client):
    client.post("/api/market/generate", json={"days": 60, "seed": 1})
    res = client.post("/api/backtests/run", json={"symbol": "NOPE", "type": "ma_crossover"})
    assert res.status_code == 404


def test_backtest_endpoint_400_for_unknown_type(client):
    client.post("/api/market/generate", json={"days": 60, "seed": 1})
    res = client.post("/api/backtests/run", json={"symbol": "ALPHA", "type": "not-a-type"})
    assert res.status_code == 400


def test_backtest_endpoint_422_for_non_positive_quantity(client):
    client.post("/api/market/generate", json={"days": 60, "seed": 1})
    res = client.post("/api/backtests/run", json={"symbol": "ALPHA", "type": "ma_crossover", "quantity": 0})
    assert res.status_code == 422


def test_backtest_endpoint_reflects_enabled_risk_settings(client):
    client.post("/api/market/generate", json={"days": 100, "seed": 1})
    client.patch("/api/risk-settings", json={"enabled": True, "max_risk_per_trade_pct": 2, "stop_loss_pct": 5, "max_allocation_pct": 100})

    res = client.post("/api/backtests/run", json={"symbol": "ALPHA", "type": "ma_crossover", "quantity": 10, "initial_capital": 100_000})
    body = res.json()
    assert body["risk_managed"] is True
    assert all(t["quantity"] != 10 for t in body["trades"]) or not body["trades"]


def test_backtest_endpoint_risk_managed_false_by_default(client):
    client.post("/api/market/generate", json={"days": 60, "seed": 1})
    res = client.post("/api/backtests/run", json={"symbol": "ALPHA", "type": "ma_crossover"})
    assert res.json()["risk_managed"] is False
    assert res.json()["stopped_out"] == 0


# ---------- date range ----------


def test_engine_start_index_skips_earlier_signals_and_starts_the_account_there():
    dates = make_dates(10)
    closes = [100, 100, 110, 110, 120, 120, 130, 130, 140, 140]
    # BUY 1, SELL 3 happen before the window; BUY 5, SELL 7 inside it
    events = [ev(1, "BUY"), ev(3, "SELL"), ev(5, "BUY"), ev(7, "SELL")]

    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=10_000, start_index=4)

    assert result.equity_curve[0].date == dates[4] and len(result.equity_curve) == 6
    assert result.equity_curve[0].value == 10_000  # nothing was held on the first traded day
    assert [(t.entry_date, t.exit_date) for t in result.trades] == [(dates[5], dates[7])]
    assert result.final_capital == pytest.approx(10_000 + 10 * (130 - 120))


def test_engine_ignores_a_sell_that_belongs_to_a_position_opened_before_the_window():
    dates = make_dates(6)
    closes = [100, 100, 110, 110, 120, 120]
    events = [ev(1, "BUY"), ev(3, "SELL")]

    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=10_000, start_index=2)

    assert result.trades == [] and result.final_capital == 10_000


def test_engine_drawdown_is_measured_only_inside_the_window():
    dates = make_dates(8)
    closes = [100, 50, 100, 100, 100, 100, 100, 100]  # a crash before the window
    events = [ev(0, "BUY"), ev(7, "SELL")]

    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=10_000, start_index=3)

    assert result.max_drawdown_pct == 0


def _ranges(client):
    client.post("/api/market/generate", json={"days": 250, "seed": 11})
    prices = client.get("/api/stocks/ALPHA/prices?full=true").json()
    return [p["date"] for p in prices]


def test_service_trims_to_the_window_but_keeps_warm_up_days_in_the_series(client, db_session):
    days = _ranges(client)
    start, end = date.fromisoformat(days[100]), date.fromisoformat(days[200])

    defn, params, dates, closes, result, _ = backtest_service.run(
        db_session, "ALPHA", "ma_crossover", {"fast": 5, "slow": 50}, 10, 100_000, start_date=start, end_date=end
    )

    assert dates[0] == date.fromisoformat(days[0]) and dates[-1] == end  # later days dropped, earlier kept
    assert result.equity_curve[0].date == start and result.equity_curve[-1].date == end
    assert len(result.equity_curve) == 101


def test_service_rejects_a_range_with_too_few_days(client, db_session):
    days = _ranges(client)
    last = date.fromisoformat(days[-1])

    with pytest.raises(InvalidStrategyError, match="date range"):
        backtest_service.run(db_session, "ALPHA", "ma_crossover", {}, 10, 100_000, start_date=last)
    with pytest.raises(InvalidStrategyError, match="date range"):
        backtest_service.run(db_session, "ALPHA", "ma_crossover", {}, 10, 100_000, end_date=date(1999, 1, 1))
    with pytest.raises(InvalidStrategyError, match="start date"):
        backtest_service.run(db_session, "ALPHA", "ma_crossover", {}, 10, 100_000, start_date=last, end_date=date.fromisoformat(days[0]))


def test_endpoint_reports_the_period_and_starts_indicator_lines_on_the_first_traded_day(client):
    days = _ranges(client)
    body = {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 5, "slow": 50}, "quantity": 10, "initial_capital": 100_000, "start_date": days[100], "end_date": days[200]}

    result = client.post("/api/backtests/run", json=body).json()

    assert (result["period_start"], result["period_end"]) == (days[100], days[200])
    assert len(result["equity_curve"]) == 101
    slow = next(s for s in result["series"] if "50" in s["name"])
    # the 50-day average already existed on day one of the window, because it warmed up beforehand
    assert slow["points"][0]["date"] == days[100] and slow["points"][-1]["date"] == days[200]
    assert all(t["entry_date"] >= days[100] for t in result["trades"])


def test_endpoint_without_dates_covers_the_whole_history(client):
    days = _ranges(client)

    result = client.post("/api/backtests/run", json={"symbol": "ALPHA", "type": "ma_crossover", "quantity": 10, "initial_capital": 100_000}).json()

    assert (result["period_start"], result["period_end"]) == (days[0], days[-1])


def test_a_window_that_starts_midway_can_differ_from_the_full_run(client):
    days = _ranges(client)
    base = {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 5, "slow": 20}, "quantity": 10, "initial_capital": 100_000}

    full = client.post("/api/backtests/run", json=base).json()
    late = client.post("/api/backtests/run", json={**base, "start_date": days[150]}).json()

    assert late["period_start"] == days[150] and len(late["equity_curve"]) == 100
    assert late["equity_curve"][0]["value"] == pytest.approx(100_000, rel=0.2)
    assert len(late["equity_curve"]) < len(full["equity_curve"])


def test_endpoint_rejects_bad_ranges(client):
    days = _ranges(client)
    base = {"symbol": "ALPHA", "type": "ma_crossover", "quantity": 10, "initial_capital": 100_000}

    backwards = client.post("/api/backtests/run", json={**base, "start_date": days[200], "end_date": days[100]})
    assert backwards.status_code == 422
    empty = client.post("/api/backtests/run", json={**base, "start_date": "2999-01-01"})
    assert empty.status_code == 400 and "date range" in empty.json()["detail"]
    junk = client.post("/api/backtests/run", json={**base, "start_date": "not-a-date"})
    assert junk.status_code == 422
