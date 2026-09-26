import random
import statistics

import pytest

from backend.app.engine.price_models import MODELS, generate_candles


def candles(model, n=250, seed=1, **overrides):
    params = {"start_price": 100.0, "volatility": 0.02, "trend": 0.0}
    params.update(overrides)
    return generate_candles(model, n, rng=random.Random(seed), **params)


def log_returns(series):
    closes = [c.close for c in series]
    import math

    return [math.log(b / a) for a, b in zip(closes, closes[1:])]


@pytest.mark.parametrize("model", MODELS)
def test_candles_are_valid_ohlcv(model):
    series = candles(model, n=300)
    assert len(series) == 300
    for c in series:
        assert c.low > 0
        assert c.low <= min(c.open, c.close)
        assert c.high >= max(c.open, c.close)
        assert c.volume > 0


def test_same_seed_is_reproducible_and_different_seed_differs():
    assert candles("random_walk", seed=5) == candles("random_walk", seed=5)
    assert candles("random_walk", seed=5) != candles("random_walk", seed=6)


def test_flat_first_open_starts_exactly_at_start_price():
    series = candles("random_walk", n=5, flat_first_open=True)
    assert series[0].open == 100.0


def test_positive_trend_rises_and_negative_trend_falls():
    up = candles("trending", trend=0.003)
    down = candles("trending", trend=-0.003)
    assert up[-1].close > 100.0
    assert down[-1].close < 100.0


def test_volatile_has_larger_swings_than_random_walk():
    volatile = statistics.stdev(log_returns(candles("volatile")))
    plain = statistics.stdev(log_returns(candles("random_walk")))
    assert volatile > 2 * plain


def test_sideways_stays_in_a_range_around_base_price():
    series = candles("sideways", n=500, seed=3)
    assert all(60 < c.close < 160 for c in series)


def test_unknown_model_and_bad_arguments_are_rejected():
    with pytest.raises(ValueError):
        candles("moonshot")
    with pytest.raises(ValueError):
        candles("random_walk", n=0)
    with pytest.raises(ValueError):
        candles("random_walk", volatility=0)
