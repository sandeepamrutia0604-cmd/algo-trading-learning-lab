"""Moving-average crossover: BUY when the fast SMA crosses above the slow SMA, SELL when it crosses below.

A signal on day i only uses closes up to and including day i.
"""

from dataclasses import dataclass

from ..engine.indicators import sma
from .base import FAST_COLOR, SLOW_COLOR, ChartSeries, ParamSpec, SignalEvent, StrategyDef

MIN_PERIOD = 2
MAX_PERIOD = 500


@dataclass(frozen=True)
class CrossoverSignal:
    index: int
    side: str  # "BUY" or "SELL"
    fast_ma: float
    slow_ma: float
    prev_fast_ma: float
    prev_slow_ma: float


def ma_crossover_signals(closes: list[float], fast: int, slow: int) -> list[CrossoverSignal]:
    if fast < MIN_PERIOD or slow > MAX_PERIOD or slow <= fast:
        raise ValueError(f"Need {MIN_PERIOD} <= fast < slow <= {MAX_PERIOD}")

    fast_ma = sma(closes, fast)
    slow_ma = sma(closes, slow)
    signals: list[CrossoverSignal] = []

    for i in range(1, len(closes)):
        if None in (fast_ma[i], slow_ma[i], fast_ma[i - 1], slow_ma[i - 1]):
            continue
        prev_diff = fast_ma[i - 1] - slow_ma[i - 1]
        diff = fast_ma[i] - slow_ma[i]
        if prev_diff <= 0 < diff:
            side = "BUY"
        elif prev_diff >= 0 > diff:
            side = "SELL"
        else:
            continue
        signals.append(
            CrossoverSignal(
                index=i,
                side=side,
                fast_ma=fast_ma[i],
                slow_ma=slow_ma[i],
                prev_fast_ma=fast_ma[i - 1],
                prev_slow_ma=slow_ma[i - 1],
            )
        )
    return signals


def crossover_checks(sig: CrossoverSignal, fast: int, slow: int) -> list[str]:
    if sig.side == "BUY":
        return [
            f"The {fast}-day average (₹{sig.fast_ma:.2f}) crossed above the {slow}-day average (₹{sig.slow_ma:.2f})",
            f"The day before it was at or below it (₹{sig.prev_fast_ma:.2f} vs ₹{sig.prev_slow_ma:.2f})",
        ]
    return [
        f"The {fast}-day average (₹{sig.fast_ma:.2f}) crossed below the {slow}-day average (₹{sig.slow_ma:.2f})",
        f"The day before it was at or above it (₹{sig.prev_fast_ma:.2f} vs ₹{sig.prev_slow_ma:.2f})",
    ]


def _generate(closes: list[float], p: dict) -> list[SignalEvent]:
    fast, slow = p["fast"], p["slow"]
    return [
        SignalEvent(
            index=s.index,
            side=s.side,
            headline=f"{fast}d {s.fast_ma:.2f} {'>' if s.side == 'BUY' else '<'} {slow}d {s.slow_ma:.2f}",
            checks=crossover_checks(s, fast, slow),
            values={"fast_ma": round(s.fast_ma, 4), "slow_ma": round(s.slow_ma, 4)},
        )
        for s in ma_crossover_signals(closes, fast, slow)
    ]


def _series(closes: list[float], p: dict) -> list[ChartSeries]:
    return [
        ChartSeries(f"SMA {p['fast']}", "price", FAST_COLOR, sma(closes, p["fast"])),
        ChartSeries(f"SMA {p['slow']}", "price", SLOW_COLOR, sma(closes, p["slow"])),
    ]


def _validate(p: dict) -> None:
    if p["fast"] >= p["slow"]:
        raise ValueError("Fast period must be smaller than slow period")


MA_CROSSOVER = StrategyDef(
    key="ma_crossover",
    label="MA Crossover",
    summary="Follows trends: buys when the short-term average climbs above the long-term average, sells when it drops below.",
    works_best="Steady trending markets.",
    struggles="Sideways markets, where it flips back and forth and loses a little on every false signal (whipsaws).",
    params=(
        ParamSpec("fast", "Fast SMA", 20, 2, 499),
        ParamSpec("slow", "Slow SMA", 50, 3, 500),
    ),
    entry_text="Fast SMA ({fast}) crosses above Slow SMA ({slow})",
    exit_text="Fast SMA crosses below Slow SMA",
    generate=_generate,
    chart_series=_series,
    name_fn=lambda p: f"MA Crossover {p['fast']}/{p['slow']}",
    validate=_validate,
)
