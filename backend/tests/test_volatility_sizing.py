from datetime import date

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.app.engine import indicators, risk_math
from backend.app.engine.backtest import RiskConfig, run_backtest
from backend.app.migrations import ensure_columns
from backend.app.models import Position, Trade
from backend.app.services import risk_service, strategy_service, trading_service
from backend.app.strategies.base import SignalEvent, StrategyDef
from backend.tests.test_risk import append_price, enable_risk, set_prices


def wiggle(size_pct, days=30, start=100.0):
    """A price that alternates up and down by `size_pct` percent a day: calm or jumpy, same drift."""
    closes, price = [start], start
    for i in range(days):
        price *= 1 + (size_pct / 100) * (1 if i % 2 == 0 else -1)
        closes.append(price)
    return closes


# ---------- the shared maths ----------


def test_a_volatility_stop_is_the_multiplier_times_daily_volatility():
    assert risk_math.volatility_stop_pct(1.5, 2.0, fallback_pct=5.0) == pytest.approx(3.0)
    assert risk_math.volatility_stop_pct(1.5, 3.0, fallback_pct=5.0) == pytest.approx(4.5)


def test_a_volatility_stop_is_kept_within_sensible_bounds():
    assert risk_math.volatility_stop_pct(0.05, 2.0, 5.0) == risk_math.MIN_STOP_PCT  # a sleepy stock: not a hair-trigger
    assert risk_math.volatility_stop_pct(40.0, 2.0, 5.0) == risk_math.MAX_STOP_PCT  # a wild one: not a stop at the floor


@pytest.mark.parametrize("volatility, multiplier", [(None, 2.0), (0.0, 2.0), (-1.0, 2.0), (1.5, 0)])
def test_without_a_usable_volatility_the_fixed_stop_is_used(volatility, multiplier):
    assert risk_math.volatility_stop_pct(volatility, multiplier, fallback_pct=5.0) == 5.0


def test_the_latest_volatility_is_the_same_figure_the_indicator_gives_for_that_day():
    closes = wiggle(1.0, days=40) + [103, 99, 104]
    series = indicators.volatility_pct(closes, 10)

    for end in (11, 20, len(closes)):
        assert risk_math.latest_volatility_pct(closes[:end], 10) == pytest.approx(series[end - 1])


def test_there_is_no_volatility_until_there_is_enough_history():
    assert risk_math.latest_volatility_pct([100, 101, 102], 5) is None
    assert risk_math.latest_volatility_pct([100, 101, 102, 103, 104, 105], 5) is not None  # window + 1 closes
    assert risk_math.latest_volatility_pct([100] * 30, 1) is None


def test_entry_stop_pct_follows_the_chosen_mode():
    closes = wiggle(2.0, days=30)

    assert risk_math.entry_stop_pct(closes, "fixed", 20, 2.0, 5.0) == 5.0
    volatility = risk_math.latest_volatility_pct(closes, 20)
    assert risk_math.entry_stop_pct(closes, "volatility", 20, 2.0, 5.0) == pytest.approx(2.0 * volatility)
    assert risk_math.entry_stop_pct(closes[:5], "volatility", 20, 2.0, 5.0) == 5.0  # too little history: fixed


def test_a_calm_stock_gets_a_bigger_position_than_a_jumpy_one_for_the_same_money_at_risk():
    calm = risk_math.entry_stop_pct(wiggle(0.4, 30), "volatility", 20, 2.0, 5.0)
    jumpy = risk_math.entry_stop_pct(wiggle(3.0, 30), "volatility", 20, 2.0, 5.0)
    calm_shares = risk_math.position_size(1_000_000, 100, 2.0, calm, 1)
    jumpy_shares = risk_math.position_size(1_000_000, 100, 2.0, jumpy, 1)

    assert calm < jumpy and calm_shares > jumpy_shares
    # what a stop-out would cost is about the same either way: 2% of the account
    assert calm_shares * 100 * calm / 100 == pytest.approx(20_000, rel=0.01)
    assert jumpy_shares * 100 * jumpy / 100 == pytest.approx(20_000, rel=0.01)


# ---------- the backtest engine ----------


def buy_at(index, sell_index=None):
    def generate(closes, params):
        events = [SignalEvent(index=index, side="BUY", headline="", checks=[], values={})]
        if sell_index is not None:
            events.append(SignalEvent(index=sell_index, side="SELL", headline="", checks=[], values={}))
        return events

    return StrategyDef(
        key="stub", label="Stub", summary="", works_best="", struggles="", params=(), entry_text="", exit_text="",
        generate=generate, chart_series=lambda closes, params: [], name_fn=lambda params: "Stub",
    )


def dates_for(closes):
    return [date(2025, 1, 1 + i) if i < 28 else date(2025, 2, i - 27) for i in range(len(closes))]


def risk(mode, **overrides):
    values = dict(enabled=True, max_risk_per_trade_pct=2.0, stop_loss_pct=5.0, max_allocation_pct=100.0, stop_mode=mode, volatility_window=10, volatility_multiplier=2.0)
    return RiskConfig(**{**values, **overrides})


def trade_after(closes, mode, **overrides):
    result = run_backtest(buy_at(len(closes) - 1), {}, dates_for(closes), closes, 10, 1_000_000, risk(mode, **overrides))
    return result.trades[0]


def test_in_volatility_mode_a_calm_stock_is_sized_larger_than_a_jumpy_one():
    calm = trade_after(wiggle(0.4, 29), "volatility")
    jumpy = trade_after(wiggle(3.0, 29), "volatility")

    assert calm.stop_pct < jumpy.stop_pct
    assert calm.quantity > jumpy.quantity
    for trade, closes in ((calm, wiggle(0.4, 29)), (jumpy, wiggle(3.0, 29))):
        expected = 2.0 * indicators.volatility_pct(closes, 10)[-1]
        assert trade.stop_pct == pytest.approx(expected) and trade.stop_pct != 5.0


def test_fixed_mode_is_unchanged_whatever_the_volatility():
    for size in (0.4, 3.0):
        closes = wiggle(size, 29)
        trade = trade_after(closes, "fixed")

        assert trade.stop_pct == 5.0
        assert trade.quantity == risk_math.position_size(1_000_000, closes[-1], 2.0, 5.0, 10, 100.0)


def test_a_buy_with_too_little_history_falls_back_to_the_fixed_stop():
    closes = wiggle(2.0, 5)  # fewer closes than the window needs

    trade = run_backtest(buy_at(5), {}, dates_for(closes), closes, 10, 1_000_000, risk("volatility", volatility_window=10)).trades[0]

    assert trade.stop_pct == 5.0


def test_the_stop_is_decided_from_what_was_known_on_the_day_of_the_buy():
    base = wiggle(1.0, 24)
    buy_day = len(base) - 1
    calm_after = base + [base[-1] * 1.001] * 5
    wild_after = base + [base[-1] * 1.3, base[-1] * 0.6, base[-1] * 1.2, base[-1] * 0.5, base[-1]]

    def entry(closes):
        return run_backtest(buy_at(buy_day), {}, dates_for(closes), closes, 10, 1_000_000, risk("volatility")).trades[0]

    assert entry(calm_after).stop_pct == entry(wild_after).stop_pct  # what happens later cannot reach back
    assert entry(calm_after).quantity == entry(wild_after).quantity


def test_the_stop_that_exits_a_trade_is_the_one_it_was_opened_with():
    calm = wiggle(0.4, 29)
    stop = 2.0 * indicators.volatility_pct(calm, 10)[-1]  # about 1.6%: much tighter than the fixed 5%
    entry_price = calm[-1]
    # a fall of 2.5%: through the volatility stop, but nowhere near the fixed 5% one
    closes = calm + [entry_price * 0.975]

    volatility = run_backtest(buy_at(len(calm) - 1), {}, dates_for(closes), closes, 10, 1_000_000, risk("volatility"))
    fixed = run_backtest(buy_at(len(calm) - 1), {}, dates_for(closes), closes, 10, 1_000_000, risk("fixed"))

    assert stop < 2.5
    assert volatility.stopped_out == 1 and volatility.trades[0].stopped_out
    assert fixed.stopped_out == 0 and fixed.trades[0].is_open


def test_a_volatility_stopped_loss_costs_about_the_risk_budget_not_more():
    jumpy = wiggle(3.0, 29)
    stop_pct = 2.0 * indicators.volatility_pct(jumpy, 10)[-1]
    closes = jumpy + [jumpy[-1] * (1 - stop_pct / 100) * 0.999]  # just through the stop

    result = run_backtest(buy_at(len(jumpy) - 1), {}, dates_for(closes), closes, 10, 1_000_000, risk("volatility"))

    assert result.stopped_out == 1
    assert result.trades[0].pnl == pytest.approx(-20_000, rel=0.1)  # about 2% of the account, however jumpy the stock


def test_risk_management_off_ignores_all_of_this():
    closes = wiggle(3.0, 29)

    trade = run_backtest(buy_at(len(closes) - 1), {}, dates_for(closes), closes, 10, 1_000_000, risk("volatility", enabled=False)).trades[0]

    assert trade.quantity == 10 and trade.stop_pct is None


# ---------- the settings ----------


def test_the_new_settings_have_defaults_that_change_nothing(client):
    settings = client.get("/api/risk-settings").json()

    assert (settings["stop_mode"], settings["volatility_window"], settings["volatility_multiplier"]) == ("fixed", 20, 2.0)


def test_the_settings_round_trip_and_are_validated(client):
    updated = client.patch("/api/risk-settings", json={"stop_mode": "volatility", "volatility_window": 30, "volatility_multiplier": 2.5}).json()

    assert (updated["stop_mode"], updated["volatility_window"], updated["volatility_multiplier"]) == ("volatility", 30, 2.5)
    assert updated["stop_loss_pct"] == 5.0  # the fixed stop is kept: it is the fallback
    assert client.get("/api/risk-settings").json() == updated
    for bad in ({"stop_mode": "magic"}, {"volatility_window": 4}, {"volatility_window": 101}, {"volatility_multiplier": 0.4}, {"volatility_multiplier": 11}):
        assert client.patch("/api/risk-settings", json=bad).status_code == 422


def test_an_old_database_gains_the_new_columns_with_the_old_behaviour(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE risk_settings (id INTEGER PRIMARY KEY, enabled BOOLEAN, stop_loss_pct FLOAT)"))
        conn.execute(text("INSERT INTO risk_settings (enabled, stop_loss_pct) VALUES (1, 5.0)"))
        conn.execute(text("CREATE TABLE trades (id INTEGER PRIMARY KEY, side VARCHAR(4))"))

    ensure_columns(engine)
    ensure_columns(engine)

    assert {"stop_mode", "volatility_window", "volatility_multiplier"} <= {c["name"] for c in inspect(engine).get_columns("risk_settings")}
    assert "stop_pct" in {c["name"] for c in inspect(engine).get_columns("trades")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT stop_mode, volatility_window, volatility_multiplier FROM risk_settings")).fetchall() == [("fixed", 20, 2.0)]


def test_a_backtest_says_when_its_stops_were_volatility_based(client):
    client.post("/api/market/generate", json={"days": 300, "seed": 11})
    run = {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 3, "slow": 8}, "quantity": 10, "initial_capital": 100_000}

    off = client.post("/api/backtests/run", json=run).json()
    client.patch("/api/risk-settings", json={"enabled": True, "max_allocation_pct": 100})
    fixed = client.post("/api/backtests/run", json=run).json()
    client.patch("/api/risk-settings", json={"stop_mode": "volatility"})
    vol = client.post("/api/backtests/run", json=run).json()

    assert (off["volatility_stops"], fixed["volatility_stops"], vol["volatility_stops"]) == (False, False, True)
    assert all(t["stop_pct"] is None for t in off["trades"])
    assert all(t["stop_pct"] == 5.0 for t in fixed["trades"])
    stops = {t["stop_pct"] for t in vol["trades"]}
    assert len(stops) > 1 and 5.0 not in stops  # each trade got its own stop


# ---------- live auto-trading ----------


def test_an_auto_trade_buy_is_sized_and_stamped_with_a_volatility_stop(db_session):
    closes = wiggle(0.3, 30) + [wiggle(0.3, 30)[-1] * 0.994]  # a small dip: RSI(2) says BUY
    set_prices(db_session, "ALPHA", closes)
    enable_risk(db_session, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=100, stop_mode="volatility", volatility_window=10, volatility_multiplier=2.0)
    strategy = strategy_service.create_strategy(db_session, "ALPHA", {"period": 2}, quantity=7, auto_trade=True, type_key="rsi")

    events = strategy_service.run_auto_strategies(db_session)

    expected_stop = risk_math.entry_stop_pct(closes, "volatility", 10, 2.0, 5.0)
    expected_qty = risk_service.position_size(db_session, closes[-1], 7, fit_allocation_cap=True, stop_pct=expected_stop)
    trade = db_session.query(Trade).filter(Trade.strategy_id == strategy.id).one()
    assert expected_stop < 5.0 and f"BUY {expected_qty} ALPHA" in events[0]
    assert trade.stop_pct == pytest.approx(expected_stop) and trade.quantity == expected_qty


def test_the_live_stop_is_the_one_stamped_at_entry_even_if_settings_change_later(db_session):
    closes = wiggle(0.3, 30)
    set_prices(db_session, "ALPHA", closes)
    enable_risk(db_session, stop_loss_pct=5, stop_mode="volatility", volatility_window=10, volatility_multiplier=2.0, max_allocation_pct=100)
    strategy = strategy_service.create_strategy(db_session, "ALPHA", {"fast": 2, "slow": 3}, quantity=10)
    stop_pct = risk_service.entry_stop_pct(db_session, closes)
    trading_service.execute_buy(db_session, "ALPHA", 10, strategy_id=strategy.id, stop_pct=stop_pct)
    entry_price = closes[-1]
    before = risk_service.stop_loss_price_for_strategy(db_session, strategy.id)

    risk_service.update_settings(db_session, volatility_multiplier=8.0, stop_loss_pct=20)  # would move a recomputed stop a long way

    assert before == pytest.approx(entry_price * (1 - stop_pct / 100))
    assert risk_service.stop_loss_price_for_strategy(db_session, strategy.id) == pytest.approx(before)


def test_a_tight_volatility_stop_exits_a_calm_stock_that_a_fixed_stop_would_hold(db_session):
    closes = wiggle(0.3, 30)
    set_prices(db_session, "ALPHA", closes)
    enable_risk(db_session, stop_loss_pct=5, stop_mode="volatility", volatility_window=10, volatility_multiplier=2.0, max_allocation_pct=100)
    strategy = strategy_service.create_strategy(db_session, "ALPHA", {"period": 2, "overbought": 95}, quantity=10, auto_trade=True, type_key="rsi")
    stop_pct = risk_service.entry_stop_pct(db_session, closes)
    trading_service.execute_buy(db_session, "ALPHA", 10, strategy_id=strategy.id, stop_pct=stop_pct)

    append_price(db_session, "ALPHA", closes[-1] * 0.97)  # down 3%: through a ~1% stop, nowhere near a 5% one
    events = strategy_service.run_auto_strategies(db_session)

    assert stop_pct < 3 and any("STOP-LOSS SELL 10 ALPHA" in e for e in events)
    assert db_session.query(Position).count() == 0


def test_trades_without_a_stamped_stop_use_the_fixed_setting(db_session):
    set_prices(db_session, "ALPHA", wiggle(0.3, 30))
    strategy = strategy_service.create_strategy(db_session, "ALPHA", {"fast": 2, "slow": 3}, quantity=10)
    trading_service.execute_buy(db_session, "ALPHA", 10, strategy_id=strategy.id)  # no stop_pct: an older or manual trade
    entry_price = wiggle(0.3, 30)[-1]
    enable_risk(db_session, stop_loss_pct=5, stop_mode="volatility")

    assert risk_service.stop_loss_price_for_strategy(db_session, strategy.id) == pytest.approx(entry_price * 0.95)


def test_risk_management_off_gives_no_stop(db_session):
    set_prices(db_session, "ALPHA", wiggle(0.3, 30))

    assert risk_service.entry_stop_pct(db_session, wiggle(0.3, 30)) is None


def test_the_trade_list_shows_the_stop_a_trade_was_opened_with(client, db_session):
    closes = wiggle(0.3, 30)
    set_prices(db_session, "ALPHA", closes)
    trading_service.execute_buy(db_session, "ALPHA", 1, stop_pct=2.5)
    trading_service.execute_buy(db_session, "ALPHA", 1)

    trades = {t["stop_pct"] for t in client.get("/api/trades").json()}

    assert trades == {2.5, None}
