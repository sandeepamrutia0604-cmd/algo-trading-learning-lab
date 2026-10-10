from datetime import date, timedelta

import pytest

from backend.app.engine.backtest import ExitConfig, RiskConfig, run_backtest
from backend.app.engine.cost_math import CostConfig
from backend.app.engine.portfolio_backtest import StockSeries, calendar, equal_weight_curve, run_portfolio_backtest
from backend.app.strategies.base import SignalEvent, StrategyDef
from backend.app.strategies.registry import get_definition


def defn_for(by_first_close):
    """A stub strategy whose signals depend on which stock it is shown: the key is the stock's first close,
    the value a list of (index, side) pairs."""
    def generate(closes, params):
        return [SignalEvent(index=i, side=side, headline="", checks=[], values={}) for i, side in by_first_close.get(closes[0], [])]

    return StrategyDef(key="stub", label="Stub", summary="", works_best="", struggles="", params=(), entry_text="",
                       exit_text="", generate=generate, chart_series=lambda c, p: [], name_fn=lambda p: "Stub")


def days(n, start=date(2025, 1, 1)):
    return [start + timedelta(days=i) for i in range(n)]


def series(symbol, closes, start=date(2025, 1, 1), step=1, start_index=0):
    ds = [start + timedelta(days=i * step) for i in range(len(closes))]
    return StockSeries(symbol, ds, list(closes), opens=[c - 0.5 for c in closes], highs=[c + 1 for c in closes],
                       lows=[c - 1 for c in closes], start_index=start_index)


# ---------- one stock gives exactly the one-stock engine's answer ----------

REAL = [("ma_crossover", {}), ("rsi", {}), ("bollinger", {}), ("breakout", {})]


def wavy(n=160):
    out, p = [], 100.0
    for i in range(n):
        p *= 1 + (0.03 if (i // 9) % 2 == 0 else -0.028)
        out.append(round(p, 2))
    return out


def same_result(a, b):
    assert [(t.entry_date, t.entry_price, t.quantity, t.exit_date, t.exit_price, t.pnl, t.exit_reason) for t in a.trades] == \
           [(t.entry_date, t.entry_price, t.quantity, t.exit_date, t.exit_price, t.pnl, t.exit_reason) for t in b.trades]
    assert [(p.date, round(p.value, 6)) for p in a.equity_curve] == [(p.date, round(p.value, 6)) for p in b.equity_curve]
    for field in ("final_capital", "skipped_buys", "stopped_out", "take_profits", "total_fees", "slippage_cost", "max_drawdown_pct"):
        assert getattr(a, field) == pytest.approx(getattr(b, field))


@pytest.mark.parametrize("key,params", REAL)
@pytest.mark.parametrize("fill_mode", ["signal_close", "next_open"])
@pytest.mark.parametrize("with_extras", [False, True])
def test_one_stock_matches_the_single_stock_engine(key, params, fill_mode, with_extras):
    defn = get_definition(key)
    p = defn.normalize(params)
    s = series("ALPHA", wavy(), start_index=20)
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=40) if with_extras else RiskConfig()
    exits = ExitConfig(stop_pct=4, target_pct=6) if with_extras else ExitConfig()
    costs = CostConfig(enabled=True, brokerage_pct=0.1, slippage_pct=0.05) if with_extras else CostConfig()
    one = run_backtest(defn, p, s.dates, s.closes, 10, 100000, risk, costs, start_index=20, fill_mode=fill_mode,
                       opens=s.opens, highs=s.highs, lows=s.lows, exits=exits)
    many = run_portfolio_backtest(defn, p, [s], 10, 100000, risk, costs, fill_mode=fill_mode, exits=exits)
    same_result(one, many)


# ---------- shared cash ----------


def test_two_stocks_share_one_pool_of_cash():
    d = defn_for({100.0: [(1, "BUY"), (4, "SELL")], 50.0: [(2, "BUY"), (5, "SELL")]})
    a = series("AAA", [100, 100, 110, 110, 120, 120, 120])
    b = series("BBB", [50, 50, 50, 60, 60, 70, 70])
    r = run_portfolio_backtest(d, {}, [a, b], 10, 10000)
    t = {x.symbol: x for x in r.trades}
    assert (t["AAA"].entry_price, t["AAA"].exit_price, t["AAA"].pnl) == (100, 120, 200)
    assert (t["BBB"].entry_price, t["BBB"].exit_price, t["BBB"].pnl) == (50, 70, 200)
    assert r.final_capital == 10400 and r.total_trades == 2 and r.peak_positions == 2
    # Day 2: AAA bought 10 at 100 (cash 9000); BBB bought 10 at 50 (cash 8500); equity = cash + holdings at every close.
    assert r.equity_curve[2].value == 8500 + 10 * 110 + 10 * 50


def test_a_buy_is_skipped_when_the_cash_has_run_out():
    d = defn_for({100.0: [(1, "BUY")], 50.0: [(1, "BUY")]})
    a = series("AAA", [100, 100, 100])
    b = series("BBB", [50, 50, 50])
    r = run_portfolio_backtest(d, {}, [a, b], 10, 1200)  # AAA takes 1000, BBB's 500 does not fit in the 200 left
    assert [t.symbol for t in r.trades] == ["AAA"]
    assert r.skipped_buys == 1 and r.skipped_by_reason["cash"] == 1


def test_same_day_buys_are_tried_in_symbol_order_whatever_order_they_were_given():
    d = defn_for({100.0: [(1, "BUY")], 50.0: [(1, "BUY")]})
    a = series("AAA", [100, 100, 100])
    b = series("BBB", [50, 50, 50])
    assert [t.symbol for t in run_portfolio_backtest(d, {}, [b, a], 10, 1200).trades] == ["AAA"]


def test_a_sell_frees_cash_for_a_buy_on_the_same_day():
    d = defn_for({100.0: [(1, "BUY"), (3, "SELL")], 50.0: [(3, "BUY")]})
    a = series("ZZZ", [100, 100, 100, 100])
    b = series("AAA", [50, 50, 50, 50])
    r = run_portfolio_backtest(d, {}, [a, b], 10, 1000)  # all the cash is in ZZZ until it sells on day 3
    assert {t.symbol for t in r.trades} == {"ZZZ", "AAA"} and r.skipped_buys == 0


def test_max_open_positions_and_allocation_limits_only_apply_with_risk_management_on():
    d = defn_for({100.0: [(1, "BUY")], 50.0: [(1, "BUY")], 20.0: [(1, "BUY")]})
    stocks = [series("AAA", [100, 100, 100]), series("BBB", [50, 50, 50]), series("CCC", [20, 20, 20])]
    off = run_portfolio_backtest(d, {}, stocks, 1, 100000, RiskConfig(enabled=False), max_open_positions=1)
    assert len(off.trades) == 3
    on = run_portfolio_backtest(d, {}, stocks, 1, 100000, RiskConfig(enabled=True), max_open_positions=2)
    assert [t.symbol for t in on.trades] == ["AAA", "BBB"] and on.skipped_by_reason["max_positions"] == 1
    capped = run_portfolio_backtest(d, {}, stocks[:1], 1000, 100000, RiskConfig(enabled=True, max_allocation_pct=20))
    assert capped.trades == [] and capped.skipped_by_reason["allocation"] == 1


def test_risk_sizing_uses_the_whole_accounts_equity():
    d = defn_for({100.0: [(1, "BUY")], 50.0: [(2, "BUY")]})
    stocks = [series("AAA", [100, 100, 100, 100]), series("BBB", [50, 50, 50, 50])]
    risk = RiskConfig(enabled=True, max_risk_per_trade_pct=1, stop_loss_pct=10, max_allocation_pct=0)
    r = run_portfolio_backtest(d, {}, stocks, 1, 10000, risk)
    # 1% of 10,000 = 100 at risk; a 10% stop on 100 is 10 a share -> 10 shares. BBB: equity is still 10,000 -> 100 / 5 = 20.
    assert {t.symbol: t.quantity for t in r.trades} == {"AAA": 10, "BBB": 20}


# ---------- calendars ----------


def test_a_stock_with_no_price_today_is_carried_at_its_last_close():
    d = defn_for({100.0: [(0, "BUY")], 10.0: []})
    a = series("AAA", [100, 110, 120, 130], step=2)  # trades every other day
    b = series("BBB", [10, 10, 10, 10, 10, 10, 10])  # every day
    r = run_portfolio_backtest(d, {}, [a, b], 10, 5000)
    assert len(r.equity_curve) == 7
    values = {p.date: p.value for p in r.equity_curve}
    assert values[date(2025, 1, 2)] == 4000 + 10 * 100  # AAA has no candle on the 2nd: still 100
    assert values[date(2025, 1, 3)] == 4000 + 10 * 110


def test_calendar_is_the_union_of_the_days_each_stock_traded_in_the_period():
    a = series("AAA", [1, 2, 3, 4], start_index=2)
    b = series("BBB", [1, 2, 3], start=date(2025, 1, 10))
    assert calendar([a, b]) == [date(2025, 1, 3), date(2025, 1, 4), date(2025, 1, 10), date(2025, 1, 11), date(2025, 1, 12)]


def test_a_sell_order_waits_for_the_next_day_that_stock_trades_in_next_open_mode():
    d = defn_for({100.0: [(0, "BUY"), (1, "SELL")], 10.0: []})
    a = series("AAA", [100, 100, 100], step=2)
    b = series("BBB", [10] * 6)
    r = run_portfolio_backtest(d, {}, [a, b], 10, 5000, fill_mode="next_open")
    assert r.trades[0].entry_date == date(2025, 1, 3) and r.trades[0].exit_date == date(2025, 1, 5)


# ---------- equal-weight baseline ----------


def test_equal_weight_baseline_splits_the_money_and_leaves_late_starters_in_cash():
    a = series("AAA", [100, 110, 120])
    b = series("BBB", [50, 50, 50, 50], start_index=1)
    ds = calendar([a, b])
    curve = equal_weight_curve([a, b], ds, 1000)
    assert curve[0] == 500 + 500  # BBB not yet trading: its half is cash
    assert curve[1] == pytest.approx(500 * 1.1 + 500)
    assert curve[2] == pytest.approx(500 * 1.2 + 500)
    assert len(curve) == len(ds)


# ---------- honesty ----------


def test_changing_a_future_price_never_changes_earlier_equity():
    defn = get_definition("ma_crossover")
    p = defn.normalize({})
    base = wavy()
    a = series("AAA", base)
    b = series("BBB", [c * 0.5 for c in base[::-1]])
    first = run_portfolio_backtest(defn, p, [a, b], 10, 100000)
    base2 = list(base)
    base2[-1] *= 3
    a2 = series("AAA", base2)
    second = run_portfolio_backtest(defn, p, [a2, b], 10, 100000)
    assert [x.value for x in first.equity_curve[:-1]] == [x.value for x in second.equity_curve[:-1]]


def test_bad_input_is_refused():
    with pytest.raises(ValueError):
        run_portfolio_backtest(get_definition("ma_crossover"), {}, [], 1, 1000)
    with pytest.raises(ValueError):
        run_portfolio_backtest(get_definition("ma_crossover"), {}, [series("A", [1, 2])], 1, 1000, fill_mode="soon")


def test_the_equivalence_series_really_trades():
    defn = get_definition("ma_crossover")
    s = series("ALPHA", wavy(), start_index=20)
    r = run_portfolio_backtest(defn, defn.normalize({}), [s], 10, 100000, RiskConfig(enabled=True, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=40),
                               exits=ExitConfig(stop_pct=4, target_pct=6))
    assert r.total_trades >= 3 and (r.stopped_out or r.take_profits)
