"""Pure technical indicators: no database, no I/O.

Every function returns a list the same length as its input, with None where there is not enough data yet.
"""

import math


def sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average. The first `period - 1` entries are None (not enough data)."""
    if period < 1:
        raise ValueError("period must be at least 1")

    result: list[float | None] = []
    window_sum = 0.0
    for i, value in enumerate(values):
        window_sum += value
        if i >= period:
            window_sum -= values[i - period]
        result.append(window_sum / period if i >= period - 1 else None)
    return result


def rolling_std(values: list[float], period: int) -> list[float | None]:
    """Population standard deviation over a rolling window."""
    if period < 1:
        raise ValueError("period must be at least 1")

    result: list[float | None] = []
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
            continue
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        result.append(math.sqrt(sum((v - mean) ** 2 for v in window) / period))
    return result


def bollinger(
    values: list[float], period: int, num_std: float
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """(middle, upper, lower) bands: SMA +/- num_std population standard deviations."""
    middle = sma(values, period)
    std = rolling_std(values, period)
    upper = [None if m is None else m + num_std * s for m, s in zip(middle, std)]
    lower = [None if m is None else m - num_std * s for m, s in zip(middle, std)]
    return middle, upper, lower


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index with Wilder smoothing. First value appears at index `period`."""
    if period < 1:
        raise ValueError("period must be at least 1")

    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result

    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    avg_gain = sum(max(c, 0.0) for c in changes[:period]) / period
    avg_loss = sum(max(-c, 0.0) for c in changes[:period]) / period
    result[period] = _rsi_value(avg_gain, avg_loss)

    for i in range(period + 1, len(values)):
        change = changes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        result[i] = _rsi_value(avg_gain, avg_loss)
    return result


def prev_max(values: list[float], n: int) -> list[float | None]:
    """Highest of the previous `n` values, not including today's."""
    return [max(values[i - n : i]) if i >= n else None for i in range(len(values))]


def prev_min(values: list[float], n: int) -> list[float | None]:
    """Lowest of the previous `n` values, not including today's."""
    return [min(values[i - n : i]) if i >= n else None for i in range(len(values))]


def volatility_pct(values: list[float], period: int) -> list[float | None]:
    """Standard deviation of the last `period` daily returns, in percent."""
    returns = [None] + [values[i] / values[i - 1] - 1 for i in range(1, len(values))]
    result: list[float | None] = []
    for i in range(len(values)):
        if i < period:
            result.append(None)
            continue
        window = returns[i - period + 1 : i + 1]
        mean = sum(window) / period
        result.append(math.sqrt(sum((r - mean) ** 2 for r in window) / period) * 100)
    return result
