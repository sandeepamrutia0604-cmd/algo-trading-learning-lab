"""Pure technical indicators: no database, no I/O."""


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
