"""Parameter optimisation: try every combination of one or two of a strategy's settings, score
each on a *training* period, and then see how the winner does on a *test* period it never saw.

That second half is the point. Picking the best of hundreds of settings on the same data you
score them on is how overfitting happens (Learn, Module 8), so the result always carries the
evidence: how the training winner fared on unseen data, where it ranks among all the settings
there, and the whole grid for both periods side by side (a real edge usually looks like a broad
bright region in both; a lucky spike on the training grid is usually gone on the test grid).

Each combination is an ordinary backtest (engine.backtest.run_backtest) under your current Risk
and Trading-cost settings, so a cell here equals the same run on the Backtests page. The test
period is traded with indicators already warmed up on the days before it, exactly like a
backtest with a From date; nothing from the test period reaches the training run.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

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


@dataclass(frozen=True)
class AxisRequest:
    param: str
    low: float
    high: float
    step: float


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
) -> dict:
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
    x_values = axis_values(x_spec, x.low, x.high, x.step)
    y_spec = _spec(defn, y.param) if y else None
    y_values = axis_values(y_spec, y.low, y.high, y.step) if y else [None]
    combinations = len(x_values) * len(y_values)
    if combinations > MAX_COMBINATIONS:
        raise InvalidStrategyError(
            f"That is {combinations} combinations; the most allowed is {MAX_COMBINATIONS}. Use bigger steps or narrower ranges."
        )

    train_start, train_end = _periods(train_start, train_end, test_start, test_end)
    candles = get_market_data_adapter(db, full_history=True).get_historical_candles(symbol)
    if len(candles) < 2:
        raise InvalidStrategyError("Not enough price history to optimise")
    risk, costs = backtest_service.run_config(db)

    train_dates, train_closes, train_i = backtest_service.window(candles, train_start, train_end)
    test_data = backtest_service.window(candles, test_start, test_end) if test_start else None

    def run(data, params):
        dates, closes, start_index = data
        return run_backtest(defn, params, dates, closes, quantity, initial_capital, risk, costs, start_index=start_index)

    train_rows: list[list[dict | None]] = []
    test_rows: list[list[dict | None]] = []
    for y_value in y_values:
        train_row, test_row = [], []
        for x_value in x_values:
            params = {**base, x.param: x_value, **({y.param: y_value} if y else {})}
            try:
                params = defn.normalize(params)
            except ValueError:  # e.g. a fast average at or above the slow one: not a real strategy
                train_row.append(None)
                test_row.append(None)
                continue
            train_row.append(_cell(metric, run((train_dates, train_closes, train_i), params)))
            test_row.append(_cell(metric, run(test_data, params)) if test_data else None)
        train_rows.append(train_row)
        test_rows.append(test_row)

    valid = [(r, c) for r, row in enumerate(train_rows) for c, cell in enumerate(row) if cell is not None]
    if not valid:
        raise InvalidStrategyError("None of those combinations is a valid set of settings. Check the ranges.")
    best_r, best_c = max(valid, key=lambda rc: train_rows[rc[0]][rc[1]]["score"])  # ties go to the first, row by row
    best_train = train_rows[best_r][best_c]
    best_test = test_rows[best_r][best_c] if test_data else None

    test_rank = test_valid = test_median = None
    if best_test is not None:
        test_scores = [cell["score"] for row in test_rows for cell in row if cell is not None]
        test_valid = len(test_scores)
        test_rank = 1 + sum(1 for score in test_scores if score > best_test["score"])
        test_median = round(median(test_scores), 4)

    def period(data, rows):
        dates, closes, start_index = data
        return {
            "start": dates[start_index],
            "end": dates[-1],
            "buy_hold_pct": round(_buy_and_hold_pct(closes, start_index), 4),
            "cells": rows,
        }

    def axis(spec, values):
        return {"name": spec.name, "label": spec.label, "values": values}

    return {
        "symbol": symbol.upper(),
        "type": defn.key,
        "type_label": defn.label,
        "metric": metric,
        "x": axis(x_spec, x_values),
        "y": axis(y_spec, y_values) if y else None,
        "train": period((train_dates, train_closes, train_i), train_rows),
        "test": period(test_data, test_rows) if test_data else None,
        "best": {
            "params": {**base, x.param: x_values[best_c], **({y.param: y_values[best_r]} if y else {})},
            "train": best_train,
            "test": best_test,
            "test_rank": test_rank,
            "test_valid": test_valid,
            "test_median_score": test_median,
        },
        "combinations": combinations,
        "valid": len(valid),
        "uses_risk": risk.enabled,
        "uses_costs": costs.enabled,
    }
