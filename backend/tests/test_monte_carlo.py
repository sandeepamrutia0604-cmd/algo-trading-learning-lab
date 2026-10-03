import math

import pytest

from backend.app.engine import monte_carlo as mc
from backend.app.live import is_change
from backend.app.services import cost_service, monte_carlo_service

RETURNS = [0.10, -0.05, 0.20, -0.10, 0.03, 0.08, -0.04, 0.12]


def product(returns):
    result = 1.0
    for r in returns:
        result *= 1 + r
    return result


# ---------- the maths ----------


def test_percentiles_interpolate_between_neighbours():
    values = [1, 2, 3, 4, 5]

    assert mc.percentile(values, 50) == 3
    assert mc.percentile(values, 0) == 1 and mc.percentile(values, 100) == 5
    assert mc.percentile(values, 95) == pytest.approx(4.8)
    assert mc.percentile([7], 30) == 7
    with pytest.raises(ValueError):
        mc.percentile([], 50)


def test_a_trades_return_is_measured_on_the_account_just_before_it_opened():
    returns = mc.account_returns(1000, [100, -110, 50])

    assert returns == pytest.approx([0.10, -110 / 1100, 50 / 990])
    # compounding those returns reproduces the account exactly
    assert 1000 * product(returns) == pytest.approx(1000 + 100 - 110 + 50)


def test_returns_stop_once_the_account_is_empty():
    assert mc.account_returns(100, [-100, 50, 50]) == [-1.0]


def test_drawdown_is_the_biggest_fall_from_a_peak():
    assert mc.max_drawdown_pct([100, 120, 90, 150, 140]) == pytest.approx(25.0)
    assert mc.max_drawdown_pct([100, 110, 120]) == 0.0
    assert mc.max_drawdown_pct([100, 0]) == 100.0


def test_an_account_cannot_go_negative():
    result = mc.simulate(1000, [-1.5, 0.5, 0.5], 100, "shuffle", seed=1)

    assert result["max_drawdown"]["max"] == 100.0
    assert result["final_return"]["min"] == -100.0


def test_a_shuffle_changes_the_path_but_never_the_total():
    result = mc.simulate(100_000, RETURNS, 500, "shuffle", seed=3)
    total = (product(RETURNS) - 1) * 100

    final = result["final_return"]
    assert final["min"] == pytest.approx(total) and final["max"] == pytest.approx(total)
    assert len(final["histogram"]["counts"]) == 1 and final["histogram"]["counts"] == [500]
    assert result["max_drawdown"]["max"] > result["max_drawdown"]["min"]  # but the drawdown does depend on the order
    assert result["probability_of_loss_pct"] in (0.0, 100.0)  # same total every time


def test_a_bootstrap_changes_the_total_too():
    result = mc.simulate(100_000, RETURNS, 800, "bootstrap", seed=3)

    final = result["final_return"]
    assert final["max"] > final["min"]
    assert 0 < result["probability_of_loss_pct"] < 100
    assert sum(final["histogram"]["counts"]) == 800 and len(final["histogram"]["counts"]) == mc.HISTOGRAM_BINS
    assert len(final["histogram"]["edges"]) == mc.HISTOGRAM_BINS + 1


def test_the_same_seed_repeats_exactly_and_another_seed_differs():
    first = mc.simulate(100_000, RETURNS, 300, "bootstrap", seed=7)

    assert first == mc.simulate(100_000, RETURNS, 300, "bootstrap", seed=7)
    assert first != mc.simulate(100_000, RETURNS, 300, "bootstrap", seed=8)


@pytest.mark.parametrize("method", ["shuffle", "bootstrap"])
def test_the_summary_is_internally_consistent(method):
    result = mc.simulate(100_000, RETURNS, 400, method, seed=2)

    for key in ("final_return", "max_drawdown"):
        p = result[key]["percentiles"]
        assert result[key]["min"] <= p["5"] <= p["25"] <= p["50"] <= p["75"] <= p["95"] <= result[key]["max"]
    assert 0 <= result["max_drawdown"]["min"] and result["max_drawdown"]["max"] <= 100
    exceed = [row["pct"] for row in result["drawdown_exceeds_pct"]]
    assert exceed == sorted(exceed, reverse=True) and all(0 <= pct <= 100 for pct in exceed)
    assert 0 <= result["original_drawdown_worse_than_pct"] <= 100 and 0 <= result["original_return_better_than_pct"] <= 100
    assert result["trade_count"] == len(RETURNS) and result["simulations"] == 400


def test_the_original_path_is_the_trades_in_their_actual_order():
    result = mc.simulate(100_000, RETURNS, 200, "shuffle", seed=1)

    assert result["original"]["return_pct"] == pytest.approx((product(RETURNS) - 1) * 100)
    path = result["fan"]["original"]
    assert path[0] == 100_000 and path[-1] == pytest.approx(100_000 * product(RETURNS))
    assert result["original"]["max_drawdown_pct"] == pytest.approx(mc.max_drawdown_pct(mc._path(100_000, RETURNS)))


def test_the_fan_starts_at_the_starting_capital_and_its_bands_are_ordered():
    fan = mc.simulate(100_000, RETURNS, 300, "bootstrap", seed=5)["fan"]

    assert fan["trade_numbers"] == list(range(len(RETURNS) + 1))
    for band in fan["bands"].values():
        assert band[0] == 100_000
    for lo, mid, hi in zip(fan["bands"]["5"], fan["bands"]["50"], fan["bands"]["95"]):
        assert lo <= mid <= hi


def test_a_long_list_of_trades_keeps_a_bounded_number_of_fan_points():
    returns = [0.01, -0.005] * 200

    fan = mc.simulate(100_000, returns, 100, "bootstrap", seed=1)["fan"]

    assert len(fan["trade_numbers"]) <= mc.MAX_FAN_POINTS
    assert fan["trade_numbers"][0] == 0 and fan["trade_numbers"][-1] == 400
    assert len(fan["original"]) == len(fan["bands"]["50"]) == len(fan["trade_numbers"])


def test_one_big_loss_costs_the_same_drawdown_wherever_it_falls():
    # compounding is multiplicative: a 30% loss is a 30% fall from the peak at any point, so every
    # ordering has the same drawdown and the actual one is never "worse than" a reshuffle
    returns = [0.05, 0.05, 0.05, 0.05, -0.30]

    result = mc.simulate(100_000, returns, 300, "shuffle", seed=1)

    assert result["max_drawdown"]["min"] == pytest.approx(30.0) and result["max_drawdown"]["max"] == pytest.approx(30.0)
    assert result["original"]["max_drawdown_pct"] == pytest.approx(30.0)
    assert result["original_drawdown_worse_than_pct"] == 0.0


@pytest.mark.parametrize("args", [(100, [], 100, "shuffle"), (100, [0.1], 0, "shuffle"), (100, [0.1], 10, "magic")])
def test_bad_inputs_are_refused(args):
    with pytest.raises(ValueError):
        mc.simulate(*args)


# ---------- through the API ----------


@pytest.fixture()
def market(client):
    client.post("/api/market/generate", json={"days": 500, "seed": 11})
    return [p["date"] for p in client.get("/api/stocks/ALPHA/prices?full=true").json()]


RUN = {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 3, "slow": 8}, "quantity": 10, "initial_capital": 100_000}


def monte(client, **change):
    body = {"request": RUN, "simulations": 500, "method": "bootstrap", "seed": 4}
    body.update(change)
    return client.post("/api/backtests/monte-carlo", json=body)


def test_it_replays_the_closed_trades_of_the_backtest(client, market):
    run = client.post("/api/backtests/run", json=RUN).json()
    closed = [t for t in run["trades"] if not t["open"]]

    result = monte(client).json()

    assert result["trade_count"] == len(closed) >= monte_carlo_service.MIN_TRADES
    realized = sum(t["pnl"] for t in closed)
    assert result["original"]["return_pct"] == pytest.approx(realized / 100_000 * 100, abs=1e-3)  # the account, trade by trade
    assert result["backtest_return_pct"] == pytest.approx(run["total_return_pct"], abs=1e-3)
    assert result["symbol"] == "ALPHA" and result["type_label"] == "MA Crossover"
    assert (result["period_start"], result["period_end"]) == (run["period_start"], run["period_end"])


def test_a_trade_still_open_at_the_end_is_left_out_and_said_so(client, market):
    run = client.post("/api/backtests/run", json=RUN).json()
    has_open = any(t["open"] for t in run["trades"])

    assert monte(client).json()["open_trade_excluded"] is has_open


def test_a_shuffle_gives_the_same_total_every_time_a_bootstrap_does_not(client, market):
    shuffled = monte(client, method="shuffle").json()
    resampled = monte(client).json()

    assert shuffled["final_return"]["min"] == pytest.approx(shuffled["final_return"]["max"])
    assert shuffled["final_return"]["min"] == pytest.approx(shuffled["original"]["return_pct"])
    assert resampled["final_return"]["max"] > resampled["final_return"]["min"]
    assert shuffled["method"] == "shuffle" and resampled["method"] == "bootstrap"


def test_a_seed_makes_it_repeatable(client, market):
    assert monte(client).json() == monte(client).json()
    assert monte(client).json() != monte(client, seed=99).json()


def test_a_date_range_is_respected(client, market):
    full = monte(client).json()
    late = monte(client, request={**RUN, "start_date": market[250]}).json()

    assert late["period_start"] == market[250] and late["trade_count"] < full["trade_count"]


def test_your_cost_settings_apply(client, db_session, market):
    plain = monte(client).json()
    cost_service.update_settings(db_session, enabled=True, slippage_pct=0.5, brokerage_pct=0.03, brokerage_cap=20.0, other_charges_pct=0.1)

    costly = monte(client).json()

    assert plain["uses_costs"] is False and costly["uses_costs"] is True
    assert costly["original"]["return_pct"] < plain["original"]["return_pct"]


def test_too_few_trades_is_explained(client, market):
    response = monte(client, request={**RUN, "params": {"fast": 20, "slow": 200}})

    assert response.status_code == 400 and "needs at least 5" in response.json()["detail"]


@pytest.mark.parametrize("change", [{"simulations": 99}, {"simulations": 5001}, {"method": "magic"}])
def test_malformed_requests_are_rejected(client, market, change):
    assert monte(client, **change).status_code == 422


def test_the_usual_backtest_refusals_apply(client, market):
    assert monte(client, request={**RUN, "symbol": "NOPE"}).status_code == 404
    assert monte(client, request={**RUN, "type": "nope"}).status_code == 400
    assert monte(client, request={**RUN, "quantity": 0}).status_code == 422


def test_a_monte_carlo_changes_nothing_so_it_is_not_announced_to_other_tabs():
    assert not is_change("POST", "/api/backtests/monte-carlo", 200)
    assert math.isfinite(mc.percentile([1.0, 2.0], 50))
