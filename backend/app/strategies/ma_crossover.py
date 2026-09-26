"""Moving-average crossover: BUY when the fast SMA crosses above the slow SMA, SELL when it crosses below.

Pure logic, no database. A signal on day i only uses closes up to and including day i.
"""

from dataclasses import dataclass

from ..engine.indicators import sma

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
