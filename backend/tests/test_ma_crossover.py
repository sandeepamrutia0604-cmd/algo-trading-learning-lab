import pytest

from backend.app.strategies.ma_crossover import ma_crossover_signals


def sides(signals):
    return [(s.index, s.side) for s in signals]


def test_crossover_matches_hand_calculation():
    # fast=2, slow=3
    # sma2: -, 5, 5, 5.5, 6.5, 6.5, 5.5, 4.5
    # sma3: -, -, 5, 5.33, 6, 6.33, 6, 5
    # day 3: fast rises above slow (was equal) -> BUY; day 6: fast falls below slow -> SELL
    signals = ma_crossover_signals([5, 5, 5, 6, 7, 6, 5, 4], fast=2, slow=3)
    assert sides(signals) == [(3, "BUY"), (6, "SELL")]

    buy = signals[0]
    assert buy.fast_ma == pytest.approx(5.5)
    assert buy.slow_ma == pytest.approx(16 / 3)
    assert buy.prev_fast_ma == pytest.approx(5.0)
    assert buy.prev_slow_ma == pytest.approx(5.0)


def test_downward_cross_gives_sell_first():
    signals = ma_crossover_signals([7, 7, 7, 6, 5], fast=2, slow=3)
    assert sides(signals) == [(3, "SELL")]


def test_flat_and_short_series_produce_no_signals():
    assert ma_crossover_signals([10.0] * 30, fast=3, slow=8) == []
    assert ma_crossover_signals([1, 2], fast=2, slow=3) == []
    assert ma_crossover_signals([], fast=2, slow=3) == []


def test_signals_alternate_between_buy_and_sell():
    closes = [10, 10, 10, 12, 14, 12, 10, 8, 10, 13, 15, 12, 9, 7, 9, 12]
    signals = ma_crossover_signals(closes, fast=2, slow=4)
    assert len(signals) >= 3
    assert all(a.side != b.side for a, b in zip(signals, signals[1:]))


def test_no_look_ahead_signals_only_use_past_data():
    closes = [10, 10, 10, 12, 14, 12, 10, 8, 10, 13, 15, 12, 9, 7, 9, 12]
    full = ma_crossover_signals(closes, fast=2, slow=4)
    for cut in range(3, len(closes) + 1):
        partial = ma_crossover_signals(closes[:cut], fast=2, slow=4)
        assert partial == [s for s in full if s.index < cut]


@pytest.mark.parametrize("fast,slow", [(1, 5), (5, 5), (10, 5), (2, 501)])
def test_invalid_periods_are_rejected(fast, slow):
    with pytest.raises(ValueError):
        ma_crossover_signals([1, 2, 3], fast, slow)
