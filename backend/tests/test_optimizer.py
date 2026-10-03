from datetime import date

import pytest

from backend.app.live import is_change
from backend.app.services import backtest_service, cost_service, optimizer_service
from backend.app.services.exceptions import InvalidStrategyError
from backend.app.strategies.base import ParamSpec

INT_SPEC = ParamSpec("fast", "Fast SMA", 20, 2, 499)
FLOAT_SPEC = ParamSpec("num_std", "Std deviations", 2.0, 0.5, 4.0, step=0.1, kind="float")


@pytest.fixture()
def market(client):
    client.post("/api/market/generate", json={"days": 400, "seed": 11})
    prices = client.get("/api/stocks/ALPHA/prices?full=true").json()
    return [p["date"] for p in prices]


def body(days, **change):
    base = {
        "symbol": "ALPHA",
        "type": "ma_crossover",
        "x": {"param": "fast", "low": 5, "high": 15, "step": 5},
        "y": {"param": "slow", "low": 20, "high": 40, "step": 10},
        "quantity": 10,
        "initial_capital": 100_000,
        "train_start": days[0],
        "train_end": days[249],
        "test_start": days[250],
        "test_end": days[-1],
    }
    return {**base, **change}


def optimise(client, days, **change):
    return client.post("/api/backtests/optimise", json=body(days, **change))


def valid_cells(period):
    return [cell for row in period["cells"] for cell in row if cell is not None]


# ---------- the values tried for one setting ----------


def test_an_integer_range_counts_up_by_the_step_and_includes_the_top():
    assert optimizer_service.axis_values(INT_SPEC, 5, 20, 5) == [5, 10, 15, 20]
    assert optimizer_service.axis_values(INT_SPEC, 5, 22, 5) == [5, 10, 15, 20]
    assert optimizer_service.axis_values(INT_SPEC, 7, 7, 1) == [7]


def test_a_float_range_has_no_drift_from_repeated_addition():
    values = optimizer_service.axis_values(FLOAT_SPEC, 1.0, 2.0, 0.1)

    assert values == [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]


@pytest.mark.parametrize(
    "low, high, step, message",
    [(5, 20, 0, "step"), (5, 20, -1, "step"), (30, 10, 5, "must not be above"), (1, 20, 5, "between"), (5, 600, 5, "between")],
)
def test_bad_ranges_are_explained(low, high, step, message):
    with pytest.raises(InvalidStrategyError, match=message):
        optimizer_service.axis_values(INT_SPEC, low, high, step)


def test_too_many_values_on_one_axis_is_refused():
    with pytest.raises(InvalidStrategyError, match="most allowed is 40"):
        optimizer_service.axis_values(INT_SPEC, 2, 499, 1)


# ---------- the grid ----------


def test_the_grid_has_one_cell_per_combination_with_rows_for_y_and_columns_for_x(client, market):
    result = optimise(client, market).json()

    assert result["x"]["values"] == [5, 10, 15] and result["y"]["values"] == [20, 30, 40]
    assert len(result["train"]["cells"]) == 3 and all(len(row) == 3 for row in result["train"]["cells"])
    assert (result["combinations"], result["valid"]) == (9, 9)
    assert (result["x"]["name"], result["y"]["name"]) == ("fast", "slow")


def test_combinations_that_are_not_real_strategies_are_left_blank(client, market):
    result = optimise(client, market, x={"param": "fast", "low": 20, "high": 40, "step": 10}, y={"param": "slow", "low": 20, "high": 40, "step": 10}).json()

    cells = result["train"]["cells"]  # rows: slow 20, 30, 40; columns: fast 20, 30, 40
    assert cells[0][0] is None and cells[0][1] is None and cells[1][1] is None  # fast >= slow
    assert cells[1][0] is not None and cells[2][0] is not None and cells[2][1] is not None
    assert result["combinations"] == 9 and result["valid"] == 3
    assert result["test"]["cells"][0][0] is None  # blank in the test grid too, in the same places


def test_a_cell_equals_the_same_run_on_the_backtests_page(client, db_session, market):
    result = optimise(client, market).json()
    best = result["best"]

    run = client.post(
        "/api/backtests/run",
        json={"symbol": "ALPHA", "type": "ma_crossover", "params": best["params"], "quantity": 10, "initial_capital": 100_000, "start_date": market[0], "end_date": market[249]},
    ).json()

    assert best["train"]["return_pct"] == pytest.approx(run["total_return_pct"], abs=1e-3)
    assert best["train"]["max_drawdown_pct"] == pytest.approx(run["max_drawdown_pct"], abs=1e-3)
    assert best["train"]["trades"] == run["total_trades"]


def test_the_test_period_is_traded_with_indicators_warmed_up_like_a_backtest_with_a_from_date(client, market):
    result = optimise(client, market).json()
    best = result["best"]

    run = client.post(
        "/api/backtests/run",
        json={"symbol": "ALPHA", "type": "ma_crossover", "params": best["params"], "quantity": 10, "initial_capital": 100_000, "start_date": market[250], "end_date": market[-1]},
    ).json()

    assert best["test"]["return_pct"] == pytest.approx(run["total_return_pct"], abs=1e-3)
    assert best["test"]["trades"] == run["total_trades"]
    assert result["test"]["start"] == market[250] and result["train"]["end"] == market[249]


def test_the_training_grid_cannot_see_the_test_period(client, market):
    with_test = optimise(client, market).json()
    without_test = optimise(client, market, test_start=None, test_end=None).json()

    assert with_test["train"]["cells"] == without_test["train"]["cells"]
    assert without_test["test"] is None and without_test["best"]["test"] is None


def test_the_best_cell_is_the_highest_scoring_one_and_params_name_it(client, market):
    result = optimise(client, market).json()

    scores = [cell["score"] for cell in valid_cells(result["train"])]
    assert result["best"]["train"]["score"] == max(scores)
    row = result["y"]["values"].index(result["best"]["params"]["slow"])
    column = result["x"]["values"].index(result["best"]["params"]["fast"])
    assert result["train"]["cells"][row][column] == result["best"]["train"]


def test_the_rank_and_median_describe_the_winner_on_the_test_period(client, market):
    result = optimise(client, market).json()
    best = result["best"]
    test_scores = sorted((cell["score"] for cell in valid_cells(result["test"])), reverse=True)

    assert best["test_valid"] == len(test_scores) == 9
    assert best["test_rank"] == 1 + sum(1 for s in test_scores if s > best["test"]["score"])
    assert best["test_median_score"] == pytest.approx(sorted(test_scores)[len(test_scores) // 2])  # nine cells: the middle one
    assert 1 <= best["test_rank"] <= best["test_valid"]


def test_buy_and_hold_is_reported_for_each_period(client, market):
    result = optimise(client, market).json()
    prices = {p["date"]: p["close"] for p in client.get("/api/stocks/ALPHA/prices?full=true").json()}

    assert result["train"]["buy_hold_pct"] == pytest.approx((prices[market[249]] / prices[market[0]] - 1) * 100, abs=1e-3)
    assert result["test"]["buy_hold_pct"] == pytest.approx((prices[market[-1]] / prices[market[250]] - 1) * 100, abs=1e-3)


def test_risk_adjusted_scores_divide_return_by_drawdown_with_a_floor(client, market):
    result = optimise(client, market, metric="risk_adjusted").json()

    for cell in valid_cells(result["train"]):
        assert cell["score"] == pytest.approx(cell["return_pct"] / max(cell["max_drawdown_pct"], 1.0), abs=1e-3)


def test_one_setting_makes_a_single_row(client, market):
    result = optimise(client, market, y=None).json()

    assert result["y"] is None and len(result["train"]["cells"]) == 1 and len(result["train"]["cells"][0]) == 3
    assert result["best"]["params"]["slow"] == 50  # the one that was not swept keeps its default


def test_fixed_settings_stay_fixed_while_others_are_swept(client, market):
    result = optimise(client, market, y=None, params={"slow": 80}).json()

    assert result["best"]["params"]["slow"] == 80 and result["best"]["params"]["fast"] in (5, 10, 15)


def test_a_strategy_with_decimal_settings_can_be_swept(client, market):
    result = optimise(client, market, type="bollinger", params={"period": 20}, x={"param": "num_std", "low": 1.0, "high": 2.0, "step": 0.5}, y=None).json()

    assert result["x"]["values"] == [1.0, 1.5, 2.0] and result["valid"] == 3


def test_your_risk_and_cost_settings_apply_like_they_do_in_a_backtest(client, db_session, market):
    plain = optimise(client, market).json()
    cost_service.update_settings(db_session, enabled=True, slippage_pct=0.5, brokerage_pct=0.03, brokerage_cap=20.0, other_charges_pct=0.1)

    costly = optimise(client, market).json()

    assert plain["uses_costs"] is False and costly["uses_costs"] is True
    assert sum(c["return_pct"] for c in valid_cells(costly["train"])) < sum(c["return_pct"] for c in valid_cells(plain["train"]))


# ---------- the dates ----------


def test_the_training_period_ends_the_day_before_the_test_starts_unless_told_otherwise(client, market):
    result = optimise(client, market, train_start=None, train_end=None).json()

    assert result["train"]["start"] == market[0]
    assert result["train"]["end"] == market[249]  # the last trading day before the test (the calendar day before may be a weekend)


def test_a_test_period_that_overlaps_the_training_period_is_refused(client, market):
    response = optimise(client, market, train_end=market[260])

    assert response.status_code == 400 and "must start after the training period ends" in response.json()["detail"]


def test_a_test_end_without_a_start_is_refused(client, market):
    response = optimise(client, market, test_start=None, test_end=market[-1])

    assert response.status_code == 400 and "test period needs a start" in response.json()["detail"]


def test_a_period_with_too_few_days_is_refused(client, market):
    response = optimise(client, market, test_start="2999-01-01", test_end=None, train_end=None)

    assert response.status_code == 400


# ---------- refusals ----------


def test_there_is_a_cap_on_how_many_combinations_run(client, market):
    response = optimise(client, market, x={"param": "fast", "low": 2, "high": 41, "step": 1}, y={"param": "slow", "low": 42, "high": 81, "step": 1})

    assert response.status_code == 400 and "most allowed is 400" in response.json()["detail"]
    assert optimizer_service.MAX_COMBINATIONS == 400


def test_custom_strategies_unknown_settings_and_duplicate_axes_are_refused(client, market):
    assert "no numeric settings" in optimise(client, market, type="custom").json()["detail"]
    assert "no setting called 'wobble'" in optimise(client, market, x={"param": "wobble", "low": 1, "high": 2, "step": 1}).json()["detail"]
    assert "two different settings" in optimise(client, market, y={"param": "fast", "low": 5, "high": 15, "step": 5}).json()["detail"]
    assert optimise(client, market, type="nope").status_code == 400
    assert optimise(client, market, symbol="NOPE").status_code == 404


def test_a_sweep_where_nothing_is_valid_says_so(client, market):
    response = optimise(client, market, x={"param": "fast", "low": 40, "high": 50, "step": 5}, y={"param": "slow", "low": 20, "high": 30, "step": 5})

    assert response.status_code == 400 and "None of those combinations" in response.json()["detail"]


@pytest.mark.parametrize("change", [{"metric": "magic"}, {"quantity": 0}, {"initial_capital": 0}, {"x": {"param": "fast", "low": 5, "high": 15, "step": 0}}])
def test_malformed_requests_are_rejected(client, market, change):
    assert optimise(client, market, **change).status_code == 422


def test_an_optimisation_changes_nothing_so_it_is_not_announced_to_other_tabs():
    assert not is_change("POST", "/api/backtests/optimise", 200)


def test_the_window_helper_matches_what_backtests_use(db_session):
    from backend.app.adapters.base import Candle

    candles = [Candle(date=date(2025, 1, d), open=1, high=1, low=1, close=float(d), volume=1) for d in range(1, 11)]

    dates, closes, start_index = backtest_service.window(candles, date(2025, 1, 4), date(2025, 1, 8))

    assert (dates[0], dates[-1], start_index) == (date(2025, 1, 1), date(2025, 1, 8), 3)
    assert closes[start_index] == 4.0
