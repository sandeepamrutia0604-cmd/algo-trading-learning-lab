import pytest

from backend.app.live import is_change
from backend.app.services import cost_service, optimizer_service
from backend.app.services.exceptions import InvalidStrategyError
from backend.app.services.optimizer_service import fold_plan


@pytest.fixture()
def days(client):
    client.post("/api/market/generate", json={"days": 600, "seed": 11})
    prices = client.get("/api/stocks/ALPHA/prices?full=true").json()
    return [p["date"] for p in prices]


def body(**change):
    base = {
        "symbol": "ALPHA",
        "type": "ma_crossover",
        "x": {"param": "fast", "low": 5, "high": 15, "step": 5},
        "y": {"param": "slow", "low": 20, "high": 40, "step": 10},
        "quantity": 10,
        "initial_capital": 100_000,
        "folds": 4,
        "train_ratio": 3,
        "mode": "rolling",
    }
    return {**base, **change}


def walk(client, **change):
    return client.post("/api/backtests/walk-forward", json=body(**change))


# ---------- the plan of windows ----------


def test_a_rolling_plan_slides_a_fixed_length_training_window_forward():
    plan = fold_plan(1000, 5, 3, "rolling")

    assert plan[0] == (0, 374, 375, 499) and plan[1] == (125, 499, 500, 624) and plan[4] == (500, 874, 875, 999)
    assert {b - a + 1 for a, b, _, _ in plan} == {375}  # the training window never changes length


def test_an_anchored_plan_always_trains_from_the_start_so_its_window_grows():
    plan = fold_plan(1000, 5, 3, "anchored")

    assert {a for a, _, _, _ in plan} == {0}
    assert [b - a + 1 for a, b, _, _ in plan] == [375, 500, 625, 750, 875]


@pytest.mark.parametrize("mode", ["rolling", "anchored"])
@pytest.mark.parametrize("n, folds, ratio", [(1000, 5, 3), (1003, 4, 2.5), (777, 3, 1), (400, 10, 3)])
def test_every_plan_is_gapless_unseen_and_ends_on_the_last_day(n, folds, ratio, mode):
    plan = fold_plan(n, folds, ratio, mode)

    assert len(plan) == folds
    for train_a, train_b, test_a, test_b in plan:
        assert 0 <= train_a <= train_b and train_b + 1 == test_a  # the test starts the day after training ends
        assert test_b >= test_a
    assert plan[-1][3] == n - 1  # the most recent data is used
    for earlier, later in zip(plan, plan[1:]):
        assert later[2] == earlier[3] + 1  # test windows follow one another with no gap or overlap
        assert later[3] - later[2] == earlier[3] - earlier[2]  # and are all the same length


def test_leftover_oldest_days_are_dropped_not_the_newest():
    assert fold_plan(1003, 5, 3, "rolling")[0][0] == 3
    assert fold_plan(1003, 5, 3, "rolling")[-1][3] == 1002


@pytest.mark.parametrize("folds", [1, 11, 0])
def test_a_plan_needs_between_two_and_ten_folds(folds):
    with pytest.raises(InvalidStrategyError, match="between 2 and 10"):
        fold_plan(1000, folds, 3, "rolling")


def test_tiny_test_windows_and_odd_inputs_are_refused():
    with pytest.raises(InvalidStrategyError, match="Not enough history"):
        fold_plan(100, 5, 3, "rolling")
    with pytest.raises(InvalidStrategyError, match="at least as long"):
        fold_plan(1000, 5, 0.5, "rolling")
    with pytest.raises(InvalidStrategyError, match="Unknown mode"):
        fold_plan(1000, 5, 3, "sideways")


# ---------- running it ----------


def test_the_result_has_one_row_per_fold_with_unseen_test_windows(client, days):
    result = walk(client).json()

    assert [f["index"] for f in result["folds"]] == [1, 2, 3, 4]
    for fold in result["folds"]:
        assert fold["train_end"] < fold["test_start"] <= fold["test_end"]
        assert set(fold["params"]) == {"fast", "slow"}
        assert fold["params"]["fast"] in (5, 10, 15) and fold["params"]["slow"] in (20, 30, 40)
        assert 1 <= fold["test_rank"] <= fold["test_valid"] == 9
    for earlier, later in zip(result["folds"], result["folds"][1:]):
        assert later["test_start"] > earlier["test_end"]
    assert result["folds"][-1]["test_end"] == days[-1]
    assert (result["summary"]["tested_from"], result["summary"]["tested_to"]) == (result["folds"][0]["test_start"], days[-1])


def test_each_folds_numbers_equal_the_same_runs_on_the_backtests_page(client, days):
    result = walk(client).json()

    for fold in result["folds"]:
        common = {"symbol": "ALPHA", "type": "ma_crossover", "params": fold["params"], "quantity": 10, "initial_capital": 100_000}
        train = client.post("/api/backtests/run", json={**common, "start_date": fold["train_start"], "end_date": fold["train_end"]}).json()
        test = client.post("/api/backtests/run", json={**common, "start_date": fold["test_start"], "end_date": fold["test_end"]}).json()
        assert fold["train"]["return_pct"] == pytest.approx(train["total_return_pct"], abs=1e-3)
        assert fold["test"]["return_pct"] == pytest.approx(test["total_return_pct"], abs=1e-3)
        assert fold["test"]["trades"] == test["total_trades"]


def test_the_winner_of_each_fold_is_the_best_on_that_folds_training_window(client, days):
    result = walk(client).json()

    for fold in result["folds"]:
        grid = client.post(
            "/api/backtests/optimise",
            json={**body(), "train_start": fold["train_start"], "train_end": fold["train_end"]},
        ).json()
        assert grid["best"]["params"] == fold["params"]
        assert grid["best"]["train"] == fold["train"]


def test_the_chained_out_of_sample_return_is_the_compounded_fold_returns(client, days):
    result = walk(client).json()

    compounded = 1.0
    for fold in result["folds"]:
        compounded *= 1 + fold["test"]["return_pct"] / 100
    assert result["summary"]["oos_return_pct"] == pytest.approx((compounded - 1) * 100, abs=1e-2)
    held = 1.0
    for fold in result["folds"]:
        held *= 1 + fold["test_buy_hold_pct"] / 100
    assert result["summary"]["oos_buy_hold_pct"] == pytest.approx((held - 1) * 100, abs=1e-2)


def test_the_equity_curve_chains_the_test_windows_without_a_jump(client, days):
    result = walk(client).json()
    equity = result["equity"]
    window_days = sum(len([d for d in days if f["test_start"] <= d <= f["test_end"]]) for f in result["folds"])

    assert len(equity["dates"]) == len(equity["strategy"]) == len(equity["buy_hold"]) == window_days
    assert equity["dates"] == sorted(set(equity["dates"]))  # in order, each day once
    assert equity["strategy"][0] == pytest.approx(100_000, rel=0.05) and equity["buy_hold"][0] == pytest.approx(100_000, rel=0.05)
    assert equity["strategy"][-1] == pytest.approx(100_000 * (1 + result["summary"]["oos_return_pct"] / 100), rel=1e-3)
    assert equity["buy_hold"][-1] == pytest.approx(100_000 * (1 + result["summary"]["oos_buy_hold_pct"] / 100), rel=1e-3)
    assert result["summary"]["oos_max_drawdown_pct"] >= 0


def test_rolling_trains_on_equal_windows_and_anchored_on_growing_ones(client, days):
    def lengths(result):
        return [len([d for d in days if f["train_start"] <= d <= f["train_end"]]) for f in result["folds"]]

    rolling = walk(client, mode="rolling").json()
    anchored = walk(client, mode="anchored").json()

    assert len(set(lengths(rolling))) == 1
    assert lengths(anchored) == sorted(lengths(anchored)) and len(set(lengths(anchored))) == 4
    assert len({f["train_start"] for f in anchored["folds"]}) == 1
    assert rolling["folds"][-1]["test_start"] == anchored["folds"][-1]["test_start"]  # the same test windows either way


def test_the_summary_counts_and_averages_what_the_folds_say(client, days):
    result = walk(client).json()
    folds, summary = result["folds"], result["summary"]
    train = [f["train"]["return_pct"] for f in folds]
    test = [f["test"]["return_pct"] for f in folds]

    assert summary["folds"] == 4
    assert summary["avg_train_return_pct"] == pytest.approx(sum(train) / 4, abs=1e-3)
    assert summary["avg_test_return_pct"] == pytest.approx(sum(test) / 4, abs=1e-3)
    assert summary["profitable_folds"] == sum(1 for r in test if r > 0)
    assert summary["beat_buy_hold_folds"] == sum(1 for f in folds if f["test"]["return_pct"] > f["test_buy_hold_pct"])
    assert summary["distinct_settings"] == len({(f["params"]["fast"], f["params"]["slow"]) for f in folds})
    if sum(train) > 0:
        assert summary["efficiency_pct"] == pytest.approx(sum(test) / sum(train) * 100, abs=0.02)
    else:
        assert summary["efficiency_pct"] is None


def test_a_date_range_limits_the_history_used(client, days):
    result = walk(client, start_date=days[100], end_date=days[499], folds=3).json()

    assert result["folds"][0]["train_start"] >= days[100]
    assert result["folds"][-1]["test_end"] == days[499]


def test_one_swept_setting_works(client, days):
    result = walk(client, y=None).json()

    assert result["y"] is None and all(set(f["params"]) == {"fast", "slow"} for f in result["folds"])
    assert all(f["test_valid"] == 3 for f in result["folds"])


def test_the_same_request_gives_the_same_answer(client, days):
    assert walk(client).json() == walk(client).json()


def test_your_cost_settings_apply(client, db_session, days):
    plain = walk(client).json()
    cost_service.update_settings(db_session, enabled=True, slippage_pct=0.5, brokerage_pct=0.03, brokerage_cap=20.0, other_charges_pct=0.1)

    costly = walk(client).json()

    assert plain["uses_costs"] is False and costly["uses_costs"] is True
    assert costly["summary"]["avg_train_return_pct"] < plain["summary"]["avg_train_return_pct"]


# ---------- refusals ----------


def test_too_little_history_for_the_folds_is_explained(client, days):
    response = walk(client, folds=10, train_ratio=10, end_date=days[300])  # 301 days: 15-day test windows

    assert response.status_code == 400 and "Not enough history" in response.json()["detail"]
    assert walk(client, start_date=days[0], end_date=days[40]).status_code == 400


@pytest.mark.parametrize("change", [{"folds": 1}, {"folds": 11}, {"train_ratio": 0.5}, {"mode": "sideways"}, {"quantity": 0}])
def test_malformed_requests_are_rejected(client, days, change):
    assert walk(client, **change).status_code == 422


def test_the_usual_optimiser_refusals_apply(client, days):
    assert "no numeric settings" in walk(client, type="custom").json()["detail"]
    assert walk(client, symbol="NOPE").status_code == 404
    assert "two different settings" in walk(client, y={"param": "fast", "low": 5, "high": 15, "step": 5}).json()["detail"]


def test_a_walk_forward_changes_nothing_so_it_is_not_announced_to_other_tabs():
    assert not is_change("POST", "/api/backtests/walk-forward", 200)
    assert optimizer_service.MAX_FOLDS == 10


# ---------- the per-fold grids (for the heatmaps) ----------


def position(result, fold):
    return result["y"]["values"].index(fold["params"]["slow"]), result["x"]["values"].index(fold["params"]["fast"])


def test_every_fold_carries_its_whole_grid_on_both_windows(client, days):
    result = walk(client).json()

    for fold in result["folds"]:
        for key in ("train_cells", "test_cells"):
            assert len(fold[key]) == 3 and all(len(row) == 3 for row in fold[key])  # slow rows by fast columns
            assert all(cell is not None for row in fold[key] for cell in row)  # 5/10/15 against 20/30/40: all valid


def test_the_winner_is_the_highest_cell_of_its_training_grid_and_its_test_cell_is_the_same_settings(client, days):
    result = walk(client).json()

    for fold in result["folds"]:
        row, column = position(result, fold)
        assert fold["train_cells"][row][column] == fold["train"]
        assert fold["test_cells"][row][column] == fold["test"]
        scores = [cell["score"] for r in fold["train_cells"] for cell in r if cell]
        assert fold["train"]["score"] == max(scores)


def test_the_rank_and_count_agree_with_the_test_grid(client, days):
    result = walk(client).json()

    for fold in result["folds"]:
        scores = [cell["score"] for r in fold["test_cells"] for cell in r if cell]
        assert fold["test_valid"] == len(scores)
        assert fold["test_rank"] == 1 + sum(1 for s in scores if s > fold["test"]["score"])


def test_a_folds_grids_equal_the_single_split_optimiser_on_the_same_windows(client, days):
    result = walk(client).json()

    for fold in result["folds"]:
        split = client.post(
            "/api/backtests/optimise",
            json={**body(), "train_start": fold["train_start"], "train_end": fold["train_end"], "test_start": fold["test_start"], "test_end": fold["test_end"]},
        ).json()
        assert split["train"]["cells"] == fold["train_cells"]
        assert split["test"]["cells"] == fold["test_cells"]


def test_combinations_that_are_not_real_strategies_are_blank_in_both_grids_of_every_fold(client, days):
    result = walk(client, x={"param": "fast", "low": 20, "high": 40, "step": 10}, y={"param": "slow", "low": 20, "high": 40, "step": 10}).json()

    for fold in result["folds"]:
        for key in ("train_cells", "test_cells"):
            cells = fold[key]  # rows: slow 20, 30, 40; columns: fast 20, 30, 40
            assert cells[0][0] is None and cells[0][1] is None and cells[1][1] is None
            assert cells[1][0] is not None and cells[2][1] is not None


def test_one_swept_setting_gives_single_row_grids(client, days):
    result = walk(client, y=None).json()

    for fold in result["folds"]:
        assert len(fold["train_cells"]) == 1 and len(fold["train_cells"][0]) == 3
        assert len(fold["test_cells"]) == 1
