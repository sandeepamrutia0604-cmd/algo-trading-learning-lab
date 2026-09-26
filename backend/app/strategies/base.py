"""Shared building blocks for strategies. Pure logic: no database, no I/O."""

from dataclasses import dataclass
from typing import Callable

FAST_COLOR = "#4c8dff"
SLOW_COLOR = "#f5a524"
PURPLE = "#a78bfa"
GREEN = "#26a69a"
RED = "#ef5350"
GRAY = "#8a94a3"


@dataclass(frozen=True)
class ParamSpec:
    name: str
    label: str
    default: float
    min: float
    max: float
    step: float = 1
    kind: str = "int"  # "int" or "float"


@dataclass(frozen=True)
class SignalEvent:
    """One BUY or SELL decision on day `index`, with the reasons that triggered it."""

    index: int
    side: str
    headline: str
    checks: list[str]
    values: dict


@dataclass(frozen=True)
class ChartSeries:
    """An indicator line to draw. `values` lines up with the price history (None where undefined)."""

    name: str
    panel: str  # "price" draws over the candles, "osc" draws in a panel underneath
    color: str
    values: list
    dash: str = "solid"
    width: float = 1.8
    fill_to_previous: bool = False
    y_range: tuple[float, float] | None = None


@dataclass(frozen=True)
class StrategyDef:
    key: str
    label: str
    summary: str
    works_best: str
    struggles: str
    params: tuple[ParamSpec, ...]
    entry_text: str
    exit_text: str
    generate: Callable[[list[float], dict], list[SignalEvent]]
    chart_series: Callable[[list[float], dict], list[ChartSeries]]
    name_fn: Callable[[dict], str]
    validate: Callable[[dict], None] | None = None

    def normalize(self, raw: dict | None) -> dict:
        raw = raw or {}
        known = {p.name for p in self.params}
        unknown = sorted(set(raw) - known)
        if unknown:
            raise ValueError(f"Unknown parameter for {self.label}: {', '.join(unknown)}")

        result: dict = {}
        for spec in self.params:
            value = raw.get(spec.name, spec.default)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{spec.label} must be a number")
            if spec.kind == "int":
                if int(value) != value:
                    raise ValueError(f"{spec.label} must be a whole number")
                value = int(value)
            else:
                value = float(value)
            if not spec.min <= value <= spec.max:
                raise ValueError(f"{spec.label} must be between {spec.min:g} and {spec.max:g}")
            result[spec.name] = value
        if self.validate:
            self.validate(result)
        return result

    def rule_text(self, params: dict) -> str:
        return f"BUY when {self.entry_text.format(**params)}; SELL when {self.exit_text.format(**params)}."

    def default_name(self, params: dict, symbol: str) -> str:
        return f"{self.name_fn(params)} on {symbol}"


def long_only_signals(
    n: int,
    entry: Callable[[int], SignalEvent | None],
    exit_: Callable[[int], SignalEvent | None],
) -> list[SignalEvent]:
    """Alternate BUY, SELL, BUY... for a long-only strategy that starts flat.

    Day i's decision only looks at data up to day i, so nothing here can peek at the future.
    """
    events: list[SignalEvent] = []
    long = False
    for i in range(n):
        event = exit_(i) if long else entry(i)
        if event is not None:
            events.append(event)
            long = not long
    return events
