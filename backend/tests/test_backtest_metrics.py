import math

import pytest

from backend.app.engine import metrics as m
from backend.app.models import SavedBacktest
from backend.app.services import analytics_service

SQRT_252 = math.sqrt(252)


# ---------- the maths, with numbers worked out by hand ----------


def test_daily_returns_are_day_over_day_changes():
    assert m.daily_returns([100, 110, 99]) == pytest.approx([0.10, -0.10])
    assert m.daily_returns([100]) == []


def test_compound_annual_growth_over_two_years_of_121_percent_is_ten_percent():
    assert m.cagr_pct(100, 121, 504) == pytest.approx(10.0)
    assert m.cagr_pct(100, 100, 252) == pytest.approx(0.0)
    assert m.cagr_pct(100, 110, 0) is None  # no time has passed
    assert m.cagr_pct(100, 0, 252) == -100.0  # wiped out


def test_volatility_is_the_daily_swing_scaled_to_a_year():
    assert m.annualised_volatility_pct([0.01, -0.01, 0.01, -0.01]) == pytest.approx(0.01 * SQRT_252 * 100)
    assert m.annualised_volatility_pct([0.01]) is None


def test_sharpe_is_average_return_per_unit_of_volatility_scaled_to_a_year():
    returns = [0.02, 0.0, 0.02, 0.0]  # average 1% a day, swinging by 1%

    assert m.sharpe_ratio(returns) == pytest.approx(SQRT_252)
    # a 25.2% a year risk-free rate is 0.1% a day, so only 0.9% of the 1% counts as excess
    assert m.sharpe_ratio(returns, risk_free_pct=25.2) == pytest.approx(0.9 * SQRT_252)


def test_sharpe_has_no_value_when_returns_never_vary_or_there_are_too_few():
    assert m.sharpe_ratio([0.01, 0.01, 0.01]) is None
    assert m.sharpe_ratio([0.01]) is None
    assert m.sharpe_ratio([]) is None


def test_sharpe_matches_the_performance_pages_calculation():
    values = [100_000, 100_500, 99_800, 101_200, 100_900, 102_000, 101_400, 103_000]
    curve = [{"date": None, "value": v} for v in values]

    assert m.sharpe_ratio(m.daily_returns(values)) == pytest.approx(analytics_service.equity_metrics(curve)["sharpe_ratio"])


def test_sortino_only_counts_falling_days_as_risk():
    returns = [0.02, -0.01, 0.02, -0.01]
    downside = math.sqrt((0.01**2 + 0.01**2) / 4)  # the two bad days, averaged over all four

    assert m.sortino_ratio(returns) == pytest.approx(0.005 / downside * SQRT_252)
    assert m.sortino_ratio(returns) > m.sharpe_ratio(returns)  # the upside swings are not punished
    assert m.sortino_ratio([0.01, 0.02, 0.01]) is None  # no downside at all


def test_calmar_is_yearly_growth_per_unit_of_worst_fall():
    assert m.calmar_ratio(20.0, 10.0) == 2.0
    assert m.calmar_ratio(20.0, 0.0) is None
    assert m.calmar_ratio(None, 10.0) is None


def test_the_longest_drawdown_counts_days_spent_below_a_previous_peak():
    assert m.longest_drawdown_days([100, 110, 100, 105, 112, 90, 95]) == 2  # two days under 110, then two under 112
    assert m.longest_drawdown_days([100, 110, 120]) == 0
    assert m.longest_drawdown_days([100, 90, 95, 96]) == 3  # still underwater at the end
    assert m.longest_drawdown_days([]) == 0


def benchmark_series(n=60):
    return [0.01 if i % 3 == 0 else -0.004 if i % 3 == 1 else 0.002 for i in range(n)]


def test_beta_alpha_for_a_strategy_that_moves_twice_as_much_as_the_benchmark():
    bench = benchmark_series()
    result = m.beta_alpha([2 * b for b in bench], bench)

    assert result["beta"] == pytest.approx(2.0) and result["correlation"] == pytest.approx(1.0)
    assert result["alpha_pct"] == pytest.approx(0.0, abs=1e-9)


def test_alpha_is_the_extra_yearly_return_beyond_what_beta_explains():
    bench = benchmark_series()
    result = m.beta_alpha([b + 0.001 for b in bench], bench)  # 0.1% a day better, otherwise identical

    assert result["beta"] == pytest.approx(1.0)
    assert result["alpha_pct"] == pytest.approx(0.001 * 252 * 100)  # 25.2% a year


def test_beta_alpha_needs_enough_overlap_and_a_moving_benchmark():
    bench = benchmark_series(10)
    assert m.beta_alpha(bench, bench) is None  # fewer than 20 shared days
    assert m.beta_alpha([0.01] * 30, [0.0] * 30) is None  # a benchmark that never moved
    assert m.beta_alpha([0.01] * 30, [0.0] * 29) is None  # lists not lined up


def test_aligned_returns_skip_days_neither_series_can_compute():
    # the third step starts from a zero on the first series, so it is skipped for both
    a, b = m.aligned_returns([100, 110, 0, 5, 6], [50, 55, 60, 62, 64])

    assert a == pytest.approx([0.10, -1.0, 0.20])
    assert b == pytest.approx([0.10, 60 / 55 - 1, 64 / 62 - 1])


def test_trade_stats_summarise_the_closed_trades():
    stats = m.trade_stats([100, -50, 200, -50, -50, -50, 300], [5, 3, 8, 2, 4, 6, 10])

    assert stats["profit_factor"] == pytest.approx(600 / 200)  # three wins worth 600 against four losses worth 200
    assert stats["average_win"] == 200 and stats["average_loss"] == -50
    assert stats["payoff_ratio"] == pytest.approx(4.0)
    assert stats["expectancy"] == pytest.approx(400 / 7)  # = win rate * average win + loss rate * average loss
    assert (stats["best_trade"], stats["worst_trade"]) == (300, -50)
    assert stats["max_consecutive_losses"] == 3
    assert stats["average_holding_days"] == pytest.approx(38 / 7)


def test_expectancy_is_win_rate_times_average_win_plus_loss_rate_times_average_loss():
    pnls = [100, -50, 200, -50, -50, -50, 300]
    stats = m.trade_stats(pnls, [1] * 7)
    win_rate = 3 / 7

    assert stats["expectancy"] == pytest.approx(win_rate * stats["average_win"] + (1 - win_rate) * stats["average_loss"])


def test_trade_stats_with_no_losses_or_no_trades_do_not_divide_by_zero():
    wins_only = m.trade_stats([10, 20], [1, 2])
    assert wins_only["profit_factor"] is None and wins_only["payoff_ratio"] is None and wins_only["average_loss"] is None

    empty = m.trade_stats([], [])
    assert empty["expectancy"] is None and empty["best_trade"] is None and empty["max_consecutive_losses"] == 0


# ---------- through the API ----------


@pytest.fixture()
def market(client):
    client.post("/api/market/generate", json={"days": 400, "seed": 11})
    prices = client.get("/api/stocks/ALPHA/prices?full=true").json()
    return {p["date"]: p for p in prices}


RUN = {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 3, "slow": 8}, "quantity": 10, "initial_capital": 100_000}


def api_run(client, **change):
    response = client.post("/api/backtests/run", json={**RUN, **change})
    assert response.status_code == 200, response.text
    return response.json()


def test_every_backtest_now_carries_the_extra_metrics(client, market):
    result = api_run(client)
    metrics = result["metrics"]

    assert metrics["trading_days"] == len(result["equity_curve"]) == 400
    assert metrics["years"] == pytest.approx(400 / 252)
    for key in ("cagr_pct", "volatility_pct", "sharpe", "sortino"):
        assert metrics[key] is not None
    assert metrics["risk_free_pct"] == 0.0 and metrics["benchmark"] is None


def test_the_numbers_match_the_equity_curve(client, market):
    result = api_run(client)
    values = [p["value"] for p in result["equity_curve"]]
    returns = m.daily_returns(values)

    assert result["metrics"]["sharpe"] == pytest.approx(m.sharpe_ratio(returns))
    assert result["metrics"]["volatility_pct"] == pytest.approx(m.annualised_volatility_pct(returns))
    expected_cagr = ((values[-1] / 100_000) ** (252 / (len(values) - 1)) - 1) * 100
    assert result["metrics"]["cagr_pct"] == pytest.approx(expected_cagr)
    assert result["metrics"]["longest_drawdown_days"] == m.longest_drawdown_days(values)
    if result["max_drawdown_pct"] > 0:
        assert result["metrics"]["calmar"] == pytest.approx(expected_cagr / result["max_drawdown_pct"])


def test_the_trade_figures_match_the_listed_trades(client, market):
    result = api_run(client)
    closed = [t for t in result["trades"] if not t["open"]]
    stats = result["metrics"]["trade_stats"]
    gross_win = sum(t["pnl"] for t in closed if t["pnl"] > 0)
    gross_loss = -sum(t["pnl"] for t in closed if t["pnl"] <= 0)

    assert stats["profit_factor"] == pytest.approx(gross_win / gross_loss)
    assert stats["expectancy"] == pytest.approx(sum(t["pnl"] for t in closed) / len(closed))
    assert stats["best_trade"] == pytest.approx(max(t["pnl"] for t in closed))
    assert stats["worst_trade"] == pytest.approx(min(t["pnl"] for t in closed))


def test_time_in_market_counts_the_days_a_position_was_held(client, market):
    result = api_run(client)
    days = sorted(market)
    held = set()
    for trade in result["trades"]:
        end = days.index(trade["exit_date"]) if not trade["open"] else len(days)
        held.update(days[days.index(trade["entry_date"]):end])

    assert result["metrics"]["days_in_market"] == len(held)
    assert result["metrics"]["exposure_pct"] == pytest.approx(len(held) / 400 * 100)
    assert 0 < result["metrics"]["exposure_pct"] <= 100


def test_a_strategy_that_never_trades_is_in_the_market_zero_percent_of_the_time(client, market):
    result = api_run(client, params={"fast": 250, "slow": 400})

    assert result["total_trades"] == 0
    assert result["metrics"]["exposure_pct"] == 0 and result["metrics"]["days_in_market"] == 0
    stats = result["metrics"]["trade_stats"]
    assert stats["profit_factor"] is None and stats["expectancy"] is None and stats["max_consecutive_losses"] == 0


def test_buy_and_hold_is_the_same_stock_over_the_same_days(client, market):
    result = api_run(client)
    days = sorted(market)
    first, last = result["equity_curve"][0]["date"], result["equity_curve"][-1]["date"]
    held = (market[last]["close"] / market[first]["close"] - 1) * 100

    assert result["metrics"]["buy_hold"]["return_pct"] == pytest.approx(held)
    assert result["metrics"]["buy_hold"]["excess_return_pct"] == pytest.approx(result["total_return_pct"] - held)
    assert (first, last) == (days[0], days[-1])


def test_a_benchmark_is_compared_over_the_days_both_have_prices_for(client, market):
    beta_prices = {p["date"]: p["close"] for p in client.get("/api/stocks/BETA/prices?full=true").json()}
    result = api_run(client, benchmark="BETA")
    bench = result["metrics"]["benchmark"]

    first, last = result["equity_curve"][0]["date"], result["equity_curve"][-1]["date"]
    assert bench["symbol"] == "BETA" and bench["days"] == 400
    assert bench["return_pct"] == pytest.approx((beta_prices[last] / beta_prices[first] - 1) * 100)
    assert bench["strategy_return_pct"] == pytest.approx(result["total_return_pct"])
    assert bench["excess_return_pct"] == pytest.approx(bench["strategy_return_pct"] - bench["return_pct"])
    assert bench["beta"] is not None and -1 <= bench["correlation"] <= 1


def test_a_benchmark_symbol_is_case_insensitive_and_an_unknown_one_is_refused(client, market):
    assert api_run(client, benchmark="beta")["metrics"]["benchmark"]["symbol"] == "BETA"
    assert client.post("/api/backtests/run", json={**RUN, "benchmark": "NOPE"}).status_code == 404


def test_a_blank_benchmark_means_none(client, market):
    assert api_run(client, benchmark="")["metrics"]["benchmark"] is None


def test_a_risk_free_rate_lowers_sharpe_and_sortino(client, market):
    free = api_run(client)["metrics"]
    paying = api_run(client, risk_free_pct=7.0)["metrics"]

    assert paying["risk_free_pct"] == 7.0
    assert paying["sharpe"] < free["sharpe"] and paying["sortino"] < free["sortino"]
    assert paying["volatility_pct"] == pytest.approx(free["volatility_pct"])  # volatility doesn't depend on it


@pytest.mark.parametrize("rate", [-1, 31])
def test_the_risk_free_rate_is_validated(client, market, rate):
    assert client.post("/api/backtests/run", json={**RUN, "risk_free_pct": rate}).status_code == 422


def test_the_metrics_work_with_next_open_fills_and_a_date_range(client, market):
    days = sorted(market)
    result = api_run(client, fill_mode="next_open", start_date=days[100], end_date=days[300])

    assert result["metrics"]["trading_days"] == 201
    assert result["metrics"]["buy_hold"]["return_pct"] == pytest.approx((market[days[300]]["close"] / market[days[100]]["close"] - 1) * 100)


def test_a_saved_backtest_keeps_its_metrics_and_an_older_one_without_them_still_loads(client, db_session, market):
    saved = client.post("/api/backtests/saved", json={"request": RUN}).json()
    detail = client.get(f"/api/backtests/saved/{saved['id']}").json()
    assert detail["result"]["metrics"]["sharpe"] is not None

    row = db_session.get(SavedBacktest, saved["id"])
    old = dict(row.result)
    old.pop("metrics")  # as saved before this feature existed
    row.result = old
    db_session.commit()

    older = client.get(f"/api/backtests/saved/{saved['id']}")
    assert older.status_code == 200 and older.json()["result"]["metrics"] is None
