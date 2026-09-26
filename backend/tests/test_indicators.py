import pytest

from backend.app.engine.indicators import sma


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
