import pytest

from backend.app.engine import exit_math as ex

# A day's candle is (open, high, low); the levels are a stop of 95 and a target of 110.
STOP, TARGET = 95.0, 110.0


def fill(open_, high, low, stop=STOP, target=TARGET):
    return ex.exit_fill(open_, high, low, stop, target)


# ---------- did the day reach a level? ----------


def test_a_quiet_day_triggers_nothing():
    assert fill(100, 103, 97) is None


def test_touching_the_stop_exactly_triggers_it():
    result = fill(100, 102, 95)
    assert (result.kind, result.price, result.gapped) == ("stop", 95.0, False)


def test_a_low_above_the_stop_does_not():
    assert fill(100, 102, 95.01) is None


def test_touching_the_target_exactly_triggers_it():
    result = fill(100, 110, 99)
    assert (result.kind, result.price, result.gapped) == ("target", 110.0, False)


def test_a_high_below_the_target_does_not():
    assert fill(100, 109.99, 99) is None


def test_the_fill_remembers_which_level_was_set():
    assert fill(100, 102, 90).level == STOP


# ---------- gaps ----------


def test_opening_below_the_stop_fills_at_the_open_not_the_stop():
    result = fill(90, 96, 88)
    assert (result.kind, result.price, result.level, result.gapped) == ("stop", 90.0, 95.0, True)


def test_opening_exactly_on_the_stop_counts_as_a_gap():
    result = fill(95, 99, 94)
    assert (result.kind, result.price, result.gapped) == ("stop", 95.0, True)


def test_opening_above_the_target_fills_at_the_open():
    result = fill(115, 118, 113)
    assert (result.kind, result.price, result.level, result.gapped) == ("target", 115.0, 110.0, True)


def test_a_gap_up_through_the_target_wins_even_if_the_day_then_fell_below_the_stop():
    # it opened at 115, so the target was hit before anything else could happen
    result = fill(115, 118, 90)
    assert (result.kind, result.price) == ("target", 115.0)


# ---------- both levels in one day ----------


def test_when_one_day_reaches_both_the_stop_wins():
    result = fill(100, 112, 93)
    assert (result.kind, result.price) == ("stop", 95.0)


# ---------- only one level set ----------


def test_with_no_target_only_the_stop_can_trigger():
    assert fill(100, 150, 99, target=None) is None
    assert fill(100, 150, 90, target=None).kind == "stop"


def test_with_no_stop_only_the_target_can_trigger():
    assert fill(100, 105, 10, stop=None) is None
    assert fill(100, 120, 99, stop=None).kind == "target"


def test_with_neither_level_nothing_triggers():
    assert fill(100, 500, 1, stop=None, target=None) is None


# ---------- checking levels before they're accepted ----------


@pytest.mark.parametrize(
    "stop, target",
    [(None, None), (95.0, None), (None, 110.0), (95.0, 110.0), (99.99, 100.01)],
)
def test_sensible_levels_are_accepted(stop, target):
    assert ex.check_levels(stop, target, 100.0) is None


@pytest.mark.parametrize("stop", [100.0, 101.0])
def test_a_stop_at_or_above_the_price_is_refused(stop):
    assert "below the current price" in ex.check_levels(stop, None, 100.0)


@pytest.mark.parametrize("target", [100.0, 99.0])
def test_a_target_at_or_below_the_price_is_refused(target):
    assert "above the current price" in ex.check_levels(None, target, 100.0)


def test_a_zero_or_negative_level_is_refused():
    assert "above zero" in ex.check_levels(0.0, None, 100.0)
    assert "above zero" in ex.check_levels(None, -5.0, 100.0)
