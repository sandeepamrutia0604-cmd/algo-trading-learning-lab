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


def test_risk_managed_backtest_blocks_a_buy_over_the_allocation_cap():
    # Risk-sized buy would spend all 1,00,000 cash (100% allocation); cap it at 50%.
    closes = [100, 100]
    dates = make_dates(len(closes))
    events = [SignalEvent(index=0, side="BUY", headline="", checks=[], values={})]
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=5, stop_loss_pct=5, max_allocation_pct=50)
    result = run_backtest(make_defn(events), {}, dates, closes, quantity=10, initial_capital=100_000, risk=risk)

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
