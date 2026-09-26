import math

import pytest

from backend.app.engine.indicators import (
    bollinger,
    prev_max,
    prev_min,
    rolling_std,
    rsi,
    sma,
    volatility_pct,
)


def test_sma_matches_hand_calculation():
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_sma_period_one_returns_the_values():
    assert sma([5.0, 7.0, 9.0], 1) == [5.0, 7.0, 9.0]


def test_sma_with_too_little_data_is_all_none():
    assert sma([1, 2], 5) == [None, None]


def test_sma_empty_input_and_invalid_period():
    assert sma([], 3) == []
    with pytest.raises(ValueError):
        sma([1, 2, 3], 0)


def test_rolling_std_is_population_std():
    result = rolling_std([1, 2, 3], 3)
    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(math.sqrt(2 / 3))


def test_bollinger_bands_match_hand_calculation():
    middle, upper, lower = bollinger([1, 2, 3], 3, 2)
    assert middle[2] == pytest.approx(2.0)
    assert upper[2] == pytest.approx(2 + 2 * math.sqrt(2 / 3))
    assert lower[2] == pytest.approx(2 - 2 * math.sqrt(2 / 3))
    assert upper[:2] == [None, None]


def test_rsi_matches_hand_calculation_with_wilder_smoothing():
    # period 3 on [10, 11, 12, 11, 12, 13]: changes +1, +1, -1, +1, +1
    # day 3: avg gain 2/3, avg loss 1/3 -> RS 2 -> RSI 66.67
    # day 4: avg gain 7/9, avg loss 2/9 -> RS 3.5 -> RSI 77.78
    # day 5: avg gain 23/27, avg loss 4/27 -> RS 5.75 -> RSI 85.19
    result = rsi([10, 11, 12, 11, 12, 13], 3)
    assert result[:3] == [None, None, None]
    assert result[3] == pytest.approx(100 - 100 / 3)
    assert result[4] == pytest.approx(100 - 100 / 4.5)
    assert result[5] == pytest.approx(100 - 100 / 6.75)


def test_rsi_extremes_and_short_input():
    assert rsi([1, 2, 3, 4, 5, 6], 3)[-1] == 100.0  # only gains
    assert rsi([6, 5, 4, 3, 2, 1], 3)[-1] == 0.0  # only losses
    assert rsi([5, 5, 5, 5, 5], 3)[-1] == 50.0  # no movement
    assert rsi([1, 2, 3], 3) == [None, None, None]


def test_prev_max_and_prev_min_exclude_today():
    assert prev_max([1, 3, 2, 5, 4], 2) == [None, None, 3, 3, 5]
    assert prev_min([4, 3, 5, 1, 2], 2) == [None, None, 3, 3, 1]


def test_volatility_pct_matches_hand_calculation():
    # returns +10% and -10%: mean 0, population std 10%
    values = [100.0, 110.0, 99.0]
    result = volatility_pct(values, 2)
    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(10.0)
    assert volatility_pct([5, 5, 5, 5], 2)[-1] == 0.0
