from backend.app.engine.alert_math import alert_hit, check_level


def test_an_above_alert_fires_when_the_high_touches_the_level():
    hit = alert_hit("above", 110, open_=100, high=110, low=99)
    assert (hit.price, hit.gapped) == (110, False)


def test_an_above_alert_does_not_fire_when_the_high_falls_short():
    assert alert_hit("above", 110, open_=100, high=109.99, low=99) is None


def test_a_below_alert_fires_when_the_low_touches_the_level():
    hit = alert_hit("below", 95, open_=100, high=101, low=95)
    assert (hit.price, hit.gapped) == (95, False)


def test_a_below_alert_does_not_fire_when_the_low_stays_above():
    assert alert_hit("below", 95, open_=100, high=101, low=95.01) is None


def test_a_gap_over_the_level_reports_the_open():
    hit = alert_hit("above", 110, open_=115, high=120, low=114)
    assert (hit.price, hit.gapped) == (115, True)


def test_a_gap_under_the_level_reports_the_open():
    hit = alert_hit("below", 95, open_=90, high=92, low=88)
    assert (hit.price, hit.gapped) == (90, True)


def test_a_level_already_crossed_is_refused():
    assert "straight away" in check_level("above", 100, 100)
    assert "straight away" in check_level("above", 99, 100)
    assert "straight away" in check_level("below", 100, 100)
    assert "straight away" in check_level("below", 101, 100)


def test_sensible_levels_and_bad_input():
    assert check_level("above", 100.01, 100) is None
    assert check_level("below", 99.99, 100) is None
    assert check_level("sideways", 100, 90) is not None
    assert check_level("below", 0, 90) is not None
