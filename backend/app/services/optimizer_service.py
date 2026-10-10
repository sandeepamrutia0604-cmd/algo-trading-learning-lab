"""Parameter optimisation, and walk-forward testing built on it.

`optimise`: try every combination of one or two of a strategy's settings, score each on a
*training* period, and then see how the winner does on a *test* period it never saw.

That second half is the point. Picking the best of hundreds of settings on the same data you
score them on is how overfitting happens (Learn, Module 8), so the result always carries the
evidence: how the training winner fared on unseen data, where it ranks among all the settings
there, and the whole grid for both periods side by side (a real edge usually looks like a broad
bright region in both; a lucky spike on the training grid is usually gone on the test grid).

`walk_forward`: one split can flatter or punish a strategy by luck, so repeat the exercise over
several windows that move through time. In each fold the settings are optimised on a training
window and the winner is traded on the window right after it, which it has never seen; the
test windows are then chained into one out-of-sample record. Training can use a rolling window
(always the same length) or an anchored one (everything since the start).

Each combination is an ordinary backtest (engine.backtest.run_backtest) under your current Risk
and Trading-cost settings, so a cell here equals the same run on the Backtests page. A test
period is traded with indicators already warmed up on the days before it, exactly like a
backtest with a From date; nothing from a test period reaches the training run that precedes it.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import NamedTuple

from sqlalchemy.orm import Session

from ..adapters import get_market_data_adapter
from ..engine.backtest import run_backtest
from ..strategies.base import ParamSpec, StrategyDef
from . import backtest_service
from .exceptions import InvalidStrategyError

MAX_COMBINATIONS = 400
MAX_AXIS_VALUES = 40
METRICS = ("return", "risk_adjusted")
DRAWDOWN_FLOOR_PCT = 1.0  # risk_adjusted = return / max(drawdown, this), so a tiny drawdown can't make a score explode

MIN_FOLDS, MAX_FOLDS = 2, 10
MIN_TEST_DAYS = 20  # a test window shorter than this says nothing
MODES = ("rolling", "anchored")


@dataclass(frozen=True)
class AxisRequest:
    param: str
    low: float
    high: float
    step: float


@dataclass(frozen=True)
class Sweep:
    """A validated set of combinations to try: which strategy, the fixed settings, the axes."""

    defn: StrategyDef
    base: dict
    x: AxisRequest
    y: AxisRequest | None
    x_spec: ParamSpec
    y_spec: ParamSpec | None
    x_values: list
    y_values: list  # [None] when there is no second setting

    @property
    def combinations(self) -> int:
        return len(self.x_values) * len(self.y_values)

    def params_at(self, row: int, column: int) -> dict:
        params = {**self.base, self.x.param: self.x_values[column]}
        if self.y:
            params[self.y.param] = self.y_values[row]
        return params


def _spec(defn: StrategyDef, name: str) -> ParamSpec:
    for spec in defn.params:
        if spec.name == name:
            return spec
    names = ", ".join(spec.name for spec in defn.params)
    raise InvalidStrategyError(f"{defn.label} has no setting called '{name}'. Its settings are: {names}")


def axis_values(spec: ParamSpec, low: float, high: float, step: float) -> list[float]:
    """The values to try for one setting: low, low+step, ... up to high (inclusive)."""
    if step <= 0:
        raise InvalidStrategyError(f"The step for {spec.label} must be greater than zero")
    if low > high:
        raise InvalidStrategyError(f"For {spec.label}, From must not be above To")
    if low < spec.min or high > spec.max:
        raise InvalidStrategyError(f"{spec.label} must stay between {spec.min:g} and {spec.max:g}")

    values: list[float] = []
    if spec.kind == "int":
        step = max(1, round(step))
        value = round(low)
        while value <= high:
            values.append(value)
            value += step
    else:
        count = int(round((high - low) / step + 1e-9))
        values = [round(low + i * step, 6) for i in range(count + 1)]
    if not values:
        raise InvalidStrategyError(f"No values to try for {spec.label}")
    if len(values) > MAX_AXIS_VALUES:
        raise InvalidStrategyError(
            f"{spec.label} would try {len(values)} values; the most allowed is {MAX_AXIS_VALUES}. Use a bigger step."
        )
    return values


def _prepare(type_key: str, fixed_params: dict | None, x: AxisRequest, y: AxisRequest | None, metric: str, quantity: int, initial_capital: float) -> Sweep:
    if metric not in METRICS:
        raise InvalidStrategyError(f"Unknown metric '{metric}'. Choose one of: {', '.join(METRICS)}")
    if quantity < 1:
        raise InvalidStrategyError("Quantity must be at least 1")
    if initial_capital <= 0:
        raise InvalidStrategyError("Initial capital must be greater than zero")
    if type_key == backtest_service.CUSTOM_TYPE:
        raise InvalidStrategyError("Custom rule strategies can't be optimised: they have no numeric settings to sweep")
    if y is not None and y.param == x.param:
        raise InvalidStrategyError("Pick two different settings to vary")

    defn = backtest_service._definition(type_key)
    base = backtest_service._normalize(defn, fixed_params)
    x_spec = _spec(defn, x.param)
    y_spec = _spec(defn, y.param) if y else None
    sweep = Sweep(
        defn=defn,
        base=base,
        x=x,
        y=y,
        x_spec=x_spec,
        y_spec=y_spec,
        x_values=axis_values(x_spec, x.low, x.high, x.step),
        y_values=axis_values(y_spec, y.low, y.high, y.step) if y else [None],
    )
    if sweep.combinations > MAX_COMBINATIONS:
        raise InvalidStrategyError(
            f"That is {sweep.combinations} combinations; the most allowed is {MAX_COMBINATIONS}. Use bigger steps or narrower ranges."
        )
    return sweep


def _score(metric: str, return_pct: float, drawdown_pct: float) -> float:
    if metric == "risk_adjusted":
        return return_pct / max(drawdown_pct, DRAWDOWN_FLOOR_PCT)
    return return_pct


def _cell(metric: str, result) -> dict:
    return {
        "score": round(_score(metric, result.total_return_pct, result.max_drawdown_pct), 4),
        "return_pct": round(result.total_return_pct, 4),
        "max_drawdown_pct": round(result.max_drawdown_pct, 4),
        "trades": result.total_trades,
    }


def _buy_and_hold_pct(closes: list[float], start_index: int) -> float:
    return (closes[-1] / closes[start_index] - 1) * 100


class Window(NamedTuple):
    """The prices of one training or test window, lined up the way `run_backtest` wants them."""

    dates: list
    closes: list
    start_index: int
    opens: list
    highs: list
    lows: list


def _data(candles: list, start: date | None, end: date | None, fill_mode: str = "signal_close") -> Window:
    dates, closes, start_index = backtest_service.window(candles, start, end)
    opens, highs, lows = backtest_service.ohlc_until(candles, end)
    return Window(dates, closes, start_index, opens, highs, lows)


def _runner(sweep: Sweep, quantity: int, initial_capital: float, risk, costs, fill_mode: str = "signal_close", exits=None):
    def run(data: Window, params):
        return run_backtest(
            sweep.defn, params, data.dates, data.closes, quantity, initial_capital, risk, costs,
            start_index=data.start_index, fill_mode=fill_mode, opens=data.opens, highs=data.highs, lows=data.lows,
            exits=exits,
        )

    return run


def _grid(sweep: Sweep, metric: str, run, train_data, test_data):
    """Backtest every combination on the training data (and the test data, if given). Rows follow
    the y values and columns the x values; a combination that is not a real strategy (a fast
    average at or above the slow one) is None in both grids."""
    train_rows: list[list[dict | None]] = []
    test_rows: list[list[dict | None]] = []
    for row in range(len(sweep.y_values)):
        train_row, test_row = [], []
        for column in range(len(sweep.x_values)):
            try:
                params = sweep.defn.normalize(sweep.params_at(row, column))
            except ValueError:
                train_row.append(None)
                test_row.append(None)
                continue
            train_row.append(_cell(metric, run(train_data, params)))
            test_row.append(_cell(metric, run(test_data, params)) if test_data else None)
        train_rows.append(train_row)
        test_rows.append(test_row)
    return train_rows, test_rows


def _best_position(rows) -> tuple[int, int, int]:
    """(row, column, valid count) of the highest training score; ties go to the first, row by row."""
    valid = [(r, c) for r, row in enumerate(rows) for c, cell in enumerate(row) if cell is not None]
    if not valid:
        raise InvalidStrategyError("None of those combinations is a valid set of settings. Check the ranges.")
    r, c = max(valid, key=lambda rc: rows[rc[0]][rc[1]]["score"])
    return r, c, len(valid)


def _test_standing(test_rows, best_test) -> tuple[int, int, float]:
    """Where the training winner ranks among every valid combination on the test data (1 = best),
    out of how many, and the median score there."""
    scores = [cell["score"] for row in test_rows for cell in row if cell is not None]
    return 1 + sum(1 for score in scores if score > best_test["score"]), len(scores), round(median(scores), 4)


def _axis_out(spec: ParamSpec, values: list) -> dict:
    return {"name": spec.name, "label": spec.label, "values": values}


def _periods(train_start, train_end, test_start, test_end):
    """Resolve the training and test dates. A test period needs a start; the training period then
    ends the day before it unless it was given an end, which must come before the test starts."""
    if test_end and not test_start:
        raise InvalidStrategyError("A test period needs a start date")
    if test_start:
        if train_end is None:
            train_end = test_start - timedelta(days=1)
        elif train_end >= test_start:
            raise InvalidStrategyError(
                "The test period must start after the training period ends, otherwise the 'unseen' data was not unseen"
            )
        if train_start and train_start > train_end:
            raise InvalidStrategyError("The training period must start before the test period does")
    return train_start, train_end


def _history(db: Session, symbol: str) -> list:
    candles = get_market_data_adapter(db, full_history=True).get_historical_candles(symbol)
    if len(candles) < 2:
        raise InvalidStrategyError("Not enough price history to optimise")
    return candles


def optimise(
    db: Session,
    symbol: str,
    type_key: str,
    fixed_params: dict | None,
    x: AxisRequest,
    y: AxisRequest | None,
    quantity: int,
    initial_capital: float,
    metric: str = "return",
    train_start: date | None = None,
    train_end: date | None = None,
    test_start: date | None = None,
    test_end: date | None = None,
    fill_mode: str = "signal_close",
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
) -> dict:
    backtest_service.check_fill_mode(fill_mode)
    exits = backtest_service.exit_config(stop_loss_pct, take_profit_pct)
    sweep = _prepare(type_key, fixed_params, x, y, metric, quantity, initial_capital)
    train_start, train_end = _periods(train_start, train_end, test_start, test_end)
    candles = _history(db, symbol)
    risk, costs = backtest_service.run_config(db)
    run = _runner(sweep, quantity, initial_capital, risk, costs, fill_mode, exits)

    train_data = _data(candles, train_start, train_end, fill_mode)
    test_data = _data(candles, test_start, test_end, fill_mode) if test_start else None
    train_rows, test_rows = _grid(sweep, metric, run, train_data, test_data)

    best_r, best_c, valid = _best_position(train_rows)
    best_train = train_rows[best_r][best_c]
    best_test = test_rows[best_r][best_c] if test_data else None
    test_rank = test_valid = test_median = None
    if best_test is not None:
        test_rank, test_valid, test_median = _test_standing(test_rows, best_test)

    def period(data: Window, rows):
        return {
            "start": data.dates[data.start_index],
            "end": data.dates[-1],
            "buy_hold_pct": round(_buy_and_hold_pct(data.closes, data.start_index), 4),
            "cells": rows,
        }

    return {
        "symbol": symbol.upper(),
        "type": sweep.defn.key,
        "type_label": sweep.defn.label,
        "metric": metric,
        "fill_mode": fill_mode,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "x": _axis_out(sweep.x_spec, sweep.x_values),
        "y": _axis_out(sweep.y_spec, sweep.y_values) if sweep.y else None,
        "train": period(train_data, train_rows),
        "test": period(test_data, test_rows) if test_data else None,
        "best": {
            "params": sweep.params_at(best_r, best_c),
            "train": best_train,
            "test": best_test,
            "test_rank": test_rank,
            "test_valid": test_valid,
            "test_median_score": test_median,
        },
        "combinations": sweep.combinations,
        "valid": valid,
        "uses_risk": risk.enabled,
        "uses_costs": costs.enabled,
    }


# ---------------------------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------------------------


def fold_plan(n: int, folds: int, train_ratio: float, mode: str) -> list[tuple[int, int, int, int]]:
    """Index windows over `n` trading days: one (train_start, train_end, test_start, test_end),
    all inclusive, per fold.

    Every test window has the same length L, and the training window is `train_ratio` times that
    (so with a ratio of 3, a fold trains on three times as many days as it then tests on). The
    test windows follow one another with no gaps and the last ends on the final day, so the most
    recent data is used and the oldest leftover days are dropped. A rolling plan trains on a
    window of fixed length that slides forward by L each fold; an anchored plan always trains
    from the first day, so its training window grows."""
    if mode not in MODES:
        raise InvalidStrategyError(f"Unknown mode '{mode}'. Choose one of: {', '.join(MODES)}")
    if not MIN_FOLDS <= folds <= MAX_FOLDS:
        raise InvalidStrategyError(f"Use between {MIN_FOLDS} and {MAX_FOLDS} folds")
    if train_ratio < 1:
        raise InvalidStrategyError("The training window must be at least as long as a test window (ratio 1 or more)")

    test_len = int(n / (train_ratio + folds))
    if test_len < MIN_TEST_DAYS:
        raise InvalidStrategyError(
            f"Not enough history for {folds} folds: each test window would be only {test_len} trading days "
            f"(at least {MIN_TEST_DAYS} are needed). Use fewer folds, a smaller ratio, or a longer date range."
        )
    train_len = int(round(train_ratio * test_len))
    offset = n - (train_len + folds * test_len)  # unused oldest days
    plan = []
    for i in range(folds):
        test_start = offset + train_len + i * test_len
        train_start = offset if mode == "anchored" else offset + i * test_len
        plan.append((train_start, test_start - 1, test_start, test_start + test_len - 1))
    return plan


def _max_drawdown_pct(values: list[float]) -> float:
    peak, worst = values[0], 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak * 100)
    return worst


def walk_forward(
    db: Session,
    symbol: str,
    type_key: str,
    fixed_params: dict | None,
    x: AxisRequest,
    y: AxisRequest | None,
    quantity: int,
    initial_capital: float,
    metric: str = "return",
    folds: int = 5,
    train_ratio: float = 3.0,
    mode: str = "rolling",
    start_date: date | None = None,
    end_date: date | None = None,
    fill_mode: str = "signal_close",
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
) -> dict:
    backtest_service.check_fill_mode(fill_mode)
    exits = backtest_service.exit_config(stop_loss_pct, take_profit_pct)
    sweep = _prepare(type_key, fixed_params, x, y, metric, quantity, initial_capital)
    candles = _history(db, symbol)
    in_range = [c.date for c in candles if (not start_date or c.date >= start_date) and (not end_date or c.date <= end_date)]
    plan = fold_plan(len(in_range), folds, train_ratio, mode)
    risk, costs = backtest_service.run_config(db)
    run = _runner(sweep, quantity, initial_capital, risk, costs, fill_mode, exits)

    fold_rows: list[dict] = []
    equity_dates: list[date] = []
    strategy_curve: list[float] = []
    hold_curve: list[float] = []
    capital = hold = initial_capital
    chosen: set[tuple] = set()

    for index, (train_a, train_b, test_a, test_b) in enumerate(plan):
        train_data = _data(candles, in_range[train_a], in_range[train_b], fill_mode)
        test_data = _data(candles, in_range[test_a], in_range[test_b], fill_mode)
        train_rows, test_rows = _grid(sweep, metric, run, train_data, test_data)
        best_r, best_c, _ = _best_position(train_rows)
        params = sweep.params_at(best_r, best_c)
        best_test = test_rows[best_r][best_c]
        rank, valid, test_median = _test_standing(test_rows, best_test)
        chosen.add(tuple(sorted(params.items())))

        # The winner's actual test-window run, to chain its equity curve onto the previous folds'.
        result = run(test_data, sweep.defn.normalize(params))
        test_dates, test_closes, test_start = test_data.dates, test_data.closes, test_data.start_index
        hold_pct = _buy_and_hold_pct(test_closes, test_start)
        for point, close in zip(result.equity_curve, test_closes[test_start:]):
            equity_dates.append(point.date)
            strategy_curve.append(capital * point.value / initial_capital)
            hold_curve.append(hold * close / test_closes[test_start])
        capital *= result.final_capital / initial_capital
        hold *= 1 + hold_pct / 100

        fold_rows.append(
            {
                "index": index + 1,
                "train_start": train_data.dates[train_data.start_index],
                "train_end": train_data.dates[-1],
                "test_start": test_dates[test_start],
                "test_end": test_dates[-1],
                "params": params,
                "train": train_rows[best_r][best_c],
                "test": best_test,
                "test_buy_hold_pct": round(hold_pct, 4),
                "test_rank": rank,
                "test_valid": valid,
                "test_median_score": test_median,
                # Every combination on this fold's training and test windows (rows follow the y
                # values, columns the x values, as in `optimise`), for the per-fold heatmaps.
                "train_cells": train_rows,
                "test_cells": test_rows,
            }
        )

    train_returns = [f["train"]["return_pct"] for f in fold_rows]
    test_returns = [f["test"]["return_pct"] for f in fold_rows]
    avg_train = sum(train_returns) / len(fold_rows)
    avg_test = sum(test_returns) / len(fold_rows)
    oos_return = (capital / initial_capital - 1) * 100
    oos_hold = (hold / initial_capital - 1) * 100

    return {
        "symbol": symbol.upper(),
        "type": sweep.defn.key,
        "type_label": sweep.defn.label,
        "metric": metric,
        "mode": mode,
        "fill_mode": fill_mode,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "train_ratio": train_ratio,
        "x": _axis_out(sweep.x_spec, sweep.x_values),
        "y": _axis_out(sweep.y_spec, sweep.y_values) if sweep.y else None,
        "folds": fold_rows,
        "summary": {
            "folds": len(fold_rows),
            "avg_train_return_pct": round(avg_train, 4),
            "avg_test_return_pct": round(avg_test, 4),
            "efficiency_pct": round(avg_test / avg_train * 100, 2) if avg_train > 0 else None,
            "oos_return_pct": round(oos_return, 4),
            "oos_buy_hold_pct": round(oos_hold, 4),
            "oos_max_drawdown_pct": round(_max_drawdown_pct(strategy_curve), 4),
            "profitable_folds": sum(1 for r in test_returns if r > 0),
            "beat_buy_hold_folds": sum(1 for f in fold_rows if f["test"]["return_pct"] > f["test_buy_hold_pct"]),
            "distinct_settings": len(chosen),
            "tested_from": fold_rows[0]["test_start"],
            "tested_to": fold_rows[-1]["test_end"],
        },
        "equity": {
            "dates": equity_dates,
            "strategy": [round(v, 2) for v in strategy_curve],
            "buy_hold": [round(v, 2) for v in hold_curve],
        },
        "combinations": sweep.combinations,
        "uses_risk": risk.enabled,
        "uses_costs": costs.enabled,
    }
