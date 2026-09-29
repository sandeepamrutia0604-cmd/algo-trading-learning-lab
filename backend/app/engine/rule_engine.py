"""Turn a user-built entry/exit condition tree into a StrategyDef, so a custom strategy plugs
into the exact same pipeline (signals, chart overlays, auto-trade, backtests) as the canned
strategy types. Pure logic: no DB, no I/O.

Rule shape (JSON, stored on Strategy.rules):
    {
        "entry": {"logic": "AND" | "OR", "conditions": [Condition, ...]},
        "exit":  {"logic": "AND" | "OR", "conditions": [Condition, ...]},
    }
Condition:
    {"left": Term, "operator": ">"|"<"|">="|"<="|"crosses_above"|"crosses_below", "right": Term}
Term (left is always an indicator; right is a number for the four comparisons above, or
another indicator for the two crossing operators):
    {"indicator": "price"} | {"indicator": "sma"|"rsi", "period": int} | {"value": number}
"""

import operator as _operator
from dataclasses import dataclass
from typing import Callable

from ..strategies.base import GRAY, GREEN, PURPLE, RED, ChartSeries, SignalEvent, StrategyDef, long_only_signals
from .indicators import rsi, sma

INDICATORS = ("price", "sma", "rsi")
LEVEL_OPERATORS = {">": _operator.gt, "<": _operator.lt, ">=": _operator.ge, "<=": _operator.le}
CROSS_OPERATORS = ("crosses_above", "crosses_below")
OPERATORS = tuple(LEVEL_OPERATORS) + CROSS_OPERATORS
OPERATOR_LABEL = {">": ">", "<": "<", ">=": "≥", "<=": "≤", "crosses_above": "crosses above", "crosses_below": "crosses below"}
PERIOD_MIN, PERIOD_MAX = 2, 500
MAX_CONDITIONS_PER_SIDE = 5
SERIES_COLORS = (PURPLE, GREEN, RED, GRAY)


def _term_series(closes: list[float], term: dict) -> list | None:
    """A per-day value series for an indicator term, or None for a plain {"value": ...} term."""
    kind = term.get("indicator")
    if kind == "price":
        return list(closes)
    if kind == "sma":
        return sma(closes, term["period"])
    if kind == "rsi":
        return rsi(closes, term["period"])
    return None


def term_label(term: dict) -> str:
    kind = term.get("indicator")
    if kind == "price":
        return "Price"
    if kind in ("sma", "rsi"):
        return f"{kind.upper()}({term['period']})"
    return f"{term['value']:g}"


def _validate_term(term: dict, *, require_value: bool) -> None:
    has_value = "value" in term
    if require_value:
        if not has_value:
            raise ValueError("This operator needs a fixed value on the right, not an indicator")
        if not isinstance(term["value"], (int, float)) or isinstance(term["value"], bool):
            raise ValueError("A condition's value must be a number")
        return
    if has_value:
        raise ValueError("This side of the condition needs an indicator, not a fixed value")
    indicator = term.get("indicator")
    if indicator not in INDICATORS:
        raise ValueError(f"Unknown indicator: {indicator!r}")
    if indicator in ("sma", "rsi"):
        period = term.get("period")
        if not isinstance(period, int) or isinstance(period, bool) or not PERIOD_MIN <= period <= PERIOD_MAX:
            raise ValueError(f"{indicator.upper()} period must be a whole number between {PERIOD_MIN} and {PERIOD_MAX}")


def validate_condition(cond: dict) -> None:
    operator_key = cond.get("operator")
    if operator_key not in OPERATORS:
        raise ValueError(f"Unknown operator: {operator_key!r}")
    left, right = cond.get("left"), cond.get("right")
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise ValueError("Each condition needs a left and right side")
    _validate_term(left, require_value=False)
    _validate_term(right, require_value=operator_key in LEVEL_OPERATORS)


def validate_side(side: dict) -> None:
    if side.get("logic") not in ("AND", "OR"):
        raise ValueError('logic must be "AND" or "OR"')
    conditions = side.get("conditions")
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= MAX_CONDITIONS_PER_SIDE:
        raise ValueError(f"Each side needs between 1 and {MAX_CONDITIONS_PER_SIDE} conditions")
    for cond in conditions:
        validate_condition(cond)


def validate_rules(rules: dict | None) -> None:
    if not isinstance(rules, dict) or "entry" not in rules or "exit" not in rules:
        raise ValueError("A custom strategy needs both entry and exit conditions")
    validate_side(rules["entry"])
    validate_side(rules["exit"])


@dataclass
class _Compiled:
    check: Callable[[int], bool]
    describe: Callable[[int], str]
    label: str


def _compile_condition(closes: list[float], cond: dict) -> _Compiled:
    left, right, op_key = cond["left"], cond["right"], cond["operator"]
    left_series = _term_series(closes, left)
    label = f"{term_label(left)} {OPERATOR_LABEL[op_key]} {term_label(right)}"

    if op_key in CROSS_OPERATORS:
        right_series = _term_series(closes, right)

        def check(i: int) -> bool:
            if i == 0:
                return False
            a0, a1, b0, b1 = left_series[i - 1], left_series[i], right_series[i - 1], right_series[i]
            if None in (a0, a1, b0, b1):
                return False
            return a0 <= b0 and a1 > b1 if op_key == "crosses_above" else a0 >= b0 and a1 < b1

        def describe(i: int) -> str:
            return f"{term_label(left)} was {left_series[i]:.2f}, {term_label(right)} was {right_series[i]:.2f}"

        return _Compiled(check, describe, label)

    value = right["value"]
    cmp_fn = LEVEL_OPERATORS[op_key]

    def check(i: int) -> bool:
        v = left_series[i]
        return v is not None and cmp_fn(v, value)

    def describe(i: int) -> str:
        v = left_series[i]
        return f"{term_label(left)} was {v:.2f} ({OPERATOR_LABEL[op_key]} {value:g})" if v is not None else f"{term_label(left)} was not yet defined"

    return _Compiled(check, describe, label)


def _compile_side(closes: list[float], side: dict) -> tuple[Callable[[int], bool], Callable[[int], list[str]], str]:
    compiled = [_compile_condition(closes, c) for c in side["conditions"]]
    logic = side["logic"]
    combine = all if logic == "AND" else any

    def check(i: int) -> bool:
        return combine(c.check(i) for c in compiled)

    def describe(i: int) -> list[str]:
        return [c.describe(i) for c in compiled]

    label = f" {logic} ".join(c.label for c in compiled)
    return check, describe, label


def evaluate(closes: list[float], rules: dict) -> list[SignalEvent]:
    entry_check, entry_describe, _ = _compile_side(closes, rules["entry"])
    exit_check, exit_describe, _ = _compile_side(closes, rules["exit"])

    def entry(i: int) -> SignalEvent | None:
        if not entry_check(i):
            return None
        return SignalEvent(index=i, side="BUY", headline="Custom rule", checks=entry_describe(i), values={})

    def exit_(i: int) -> SignalEvent | None:
        if not exit_check(i):
            return None
        return SignalEvent(index=i, side="SELL", headline="Custom rule", checks=exit_describe(i), values={})

    return long_only_signals(len(closes), entry, exit_)


def build_chart_series(closes: list[float], rules: dict) -> list[ChartSeries]:
    seen: set[tuple] = set()
    series: list[ChartSeries] = []
    color_i = 0
    for cond in rules["entry"]["conditions"] + rules["exit"]["conditions"]:
        for term in (cond["left"], cond["right"]):
            kind = term.get("indicator")
            if kind not in ("sma", "rsi"):
                continue
            key = (kind, term["period"])
            if key in seen:
                continue
            seen.add(key)
            if kind == "sma":
                series.append(ChartSeries(f"SMA {term['period']}", "price", SERIES_COLORS[color_i % len(SERIES_COLORS)], sma(closes, term["period"])))
                color_i += 1
            else:
                series.append(ChartSeries(f"RSI {term['period']}", "osc", PURPLE, rsi(closes, term["period"]), y_range=(0, 100)))
    return series


def rule_side_text(side: dict) -> str:
    return f" {side['logic']} ".join(f"{term_label(c['left'])} {OPERATOR_LABEL[c['operator']]} {term_label(c['right'])}" for c in side["conditions"])


def build_definition(rules: dict) -> StrategyDef:
    return StrategyDef(
        key="custom",
        label="Custom",
        summary="A strategy built from your own entry and exit conditions.",
        works_best="Whatever market condition your rules were designed to catch — check with Backtests.",
        struggles="Custom logic isn't validated against any market regime; back-test before auto-trading it.",
        params=(),
        entry_text=rule_side_text(rules["entry"]),
        exit_text=rule_side_text(rules["exit"]),
        generate=lambda closes, params: evaluate(closes, rules),
        chart_series=lambda closes, params: build_chart_series(closes, rules),
        name_fn=lambda params: "Custom strategy",
    )
