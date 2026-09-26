"""Pure price-series generators: no database, no I/O."""

import math
import random
from dataclasses import dataclass

MODELS = ("random_walk", "trending", "volatile", "sideways")

VOLATILE_MULTIPLIER = 2.5
TREND_MOMENTUM = 0.3
MEAN_REVERSION = 0.1
MIN_PRICE = 0.01
BASE_VOLUME = 100_000


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: int


def generate_candles(
    model: str,
    n: int,
    start_price: float,
    volatility: float,
    trend: float,
    rng: random.Random,
    *,
    base_price: float | None = None,
    prev_return: float = 0.0,
    flat_first_open: bool = False,
) -> list[Candle]:
    """Generate `n` daily candles continuing from `start_price` (the previous close).

    Daily log-return per model (sigma = volatility, drift = trend):
      random_walk: drift + sigma * noise
      trending:    drift + 0.3 * previous_return + sigma * noise   (momentum)
      volatile:    drift + 2.5 * sigma * noise
      sideways:    drift - 0.1 * ln(price / base) + sigma * noise  (pulled back to base)
    """
    if model not in MODELS:
        raise ValueError(f"Unknown price model: {model}")
    if n < 1:
        raise ValueError("n must be at least 1")
    if start_price <= 0 or volatility <= 0:
        raise ValueError("start_price and volatility must be positive")

    base = base_price if base_price else start_price
    sigma = volatility * (VOLATILE_MULTIPLIER if model == "volatile" else 1.0)

    prev_close = start_price
    r_prev = prev_return
    candles: list[Candle] = []

    for i in range(n):
        noise = rng.gauss(0, 1)
        if model == "trending":
            r = trend + TREND_MOMENTUM * r_prev + sigma * noise
        elif model == "sideways":
            r = trend - MEAN_REVERSION * math.log(prev_close / base) + sigma * noise
        else:
            r = trend + sigma * noise

        close = prev_close * math.exp(r)
        if flat_first_open and i == 0:
            open_ = prev_close
        else:
            open_ = prev_close * math.exp(0.25 * sigma * rng.gauss(0, 1))

        high = max(open_, close) * math.exp(abs(rng.gauss(0, 1)) * 0.5 * sigma)
        low = min(open_, close) * math.exp(-abs(rng.gauss(0, 1)) * 0.5 * sigma)
        volume = int(BASE_VOLUME * math.exp(0.3 * rng.gauss(0, 1)) * (1 + abs(r) / sigma))

        o = max(round(open_, 2), MIN_PRICE)
        c = max(round(close, 2), MIN_PRICE)
        h = max(round(high, 2), o, c)
        lo = max(min(round(low, 2), o, c), MIN_PRICE)

        candles.append(Candle(open=o, high=h, low=lo, close=c, volume=volume))
        prev_close = c
        r_prev = r

    return candles
