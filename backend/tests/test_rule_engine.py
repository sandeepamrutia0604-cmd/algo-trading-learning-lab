import random

import pytest

from backend.app.engine import rule_engine
from backend.app.strategies.ma_crossover import ma_crossover_signals


def price(op, value):
    return {"left": {"indicator": "price"}, "operator": op, "right": {"value": value}}


def crossing(op, fast, slow):
    return {
        "left": {"indicator": "sma", "period": fast},
        "operator": op,
        "right": {"indicator": "sma", "period": slow},
    }


def side(logic, conditions):
    return {"logic": logic, "conditions": conditions}


def random_walk(n=200, seed=3, vol=0.015):
    rng = random.Random(seed)
    closes = [100.0]
    for _ in range(n):
        closes.append(closes[-1] * (1 + rng.gauss(0, vol)))
    return closes


# ---------- evaluate(): level conditions ----------


def test_evaluate_level_conditions_alternate_buy_sell_flat_to_flat():
    closes = [100, 105, 95, 80, 120]
    rules = {"entry": side("AND", [price(">", 100)]), "exit": side("AND", [price("<", 90)])}
    events = rule_engine.evaluate(closes, rules)
    assert [(e.index, e.side) for e in events] == [(1, "BUY"), (3, "SELL"), (4, "BUY")]


def test_evaluate_never_triggers_when_conditions_never_hold():
    closes = [10, 11, 12, 13]
    rules = {"entry": side("AND", [price(">", 1000)]), "exit": side("AND", [price("<", -1000)])}
    assert rule_engine.evaluate(closes, rules) == []


def test_evaluate_checks_text_describes_the_triggering_condition():
    closes = [100, 105]
    rules = {"entry": side("AND", [price(">", 100)]), "exit": side("AND", [price("<", 1)])}
    events = rule_engine.evaluate(closes, rules)
    assert len(events) == 1
    assert "Price was 105.00" in events[0].checks[0]


# ---------- AND / OR combinators ----------


def test_and_combinator_requires_every_condition_on_the_same_day():
    closes = [10, 20, 30, 40, 50]
    check, _, _ = rule_engine._compile_side(closes, side("AND", [price(">", 25), price("<", 45)]))
    assert [check(i) for i in range(5)] == [False, False, True, True, False]


def test_or_combinator_needs_only_one_condition_true():
    closes = [10, 20, 30, 40, 50]
    check, _, _ = rule_engine._compile_side(closes, side("OR", [price(">", 25), price("<", 45)]))
    assert [check(i) for i in range(5)] == [True, True, True, True, True]


# ---------- crossing conditions ----------


def _filter_long_only(raw):
    """MA_CROSSOVER's generate() emits every raw crossing unfiltered; the rule engine runs
    crossing conditions through long_only_signals, so replicate that same state filter here."""
    result, long = [], False
    for index, side_ in raw:
        if side_ == "BUY" and not long:
            result.append((index, side_))
            long = True
        elif side_ == "SELL" and long:
            result.append((index, side_))
            long = False
    return result


def test_crossing_condition_matches_the_canned_ma_crossover_signal_indices():
    closes = random_walk()
    fast, slow = 5, 12
    raw = [(s.index, s.side) for s in ma_crossover_signals(closes, fast, slow)]
    expected = _filter_long_only(raw)

    rules = {
        "entry": side("AND", [crossing("crosses_above", fast, slow)]),
        "exit": side("AND", [crossing("crosses_below", fast, slow)]),
    }
    events = rule_engine.evaluate(closes, rules)
    assert [(e.index, e.side) for e in events] == expected
    assert len(expected) > 3  # sanity: the random walk actually produced several crossings


# ---------- validation ----------


def test_validate_rules_accepts_a_well_formed_tree():
    rule_engine.validate_rules(
        {
            "entry": side("AND", [price(">", 100), crossing("crosses_above", 20, 50)]),
            "exit": side("OR", [price("<", 90), crossing("crosses_below", 20, 50)]),
        }
    )


@pytest.mark.parametrize(
    "rules",
    [
        None,
        {},
        {"entry": side("AND", [price(">", 1)])},  # missing exit
        {"entry": side("BOTH", [price(">", 1)]), "exit": side("AND", [price("<", 1)])},  # bad logic
        {"entry": side("AND", []), "exit": side("AND", [price("<", 1)])},  # empty conditions
        {"entry": side("AND", [price(">", 1)] * 6), "exit": side("AND", [price("<", 1)])},  # too many
        {"entry": side("AND", [{"left": {"value": 1}, "operator": ">", "right": {"value": 2}}]), "exit": side("AND", [price("<", 1)])},  # value on left
        {"entry": side("AND", [{"left": {"indicator": "price"}, "operator": ">", "right": {"indicator": "price"}}]), "exit": side("AND", [price("<", 1)])},  # level op needs a value on the right
        {"entry": side("AND", [crossing("crosses_above", 20, 50)]), "exit": side("AND", [{"left": {"indicator": "sma", "period": 20}, "operator": "crosses_below", "right": {"value": 5}}])},  # crossing needs an indicator on the right
        {"entry": side("AND", [{"left": {"indicator": "sma", "period": 1}, "operator": ">", "right": {"value": 1}}]), "exit": side("AND", [price("<", 1)])},  # period out of range
        {"entry": side("AND", [{"left": {"indicator": "bogus"}, "operator": ">", "right": {"value": 1}}]), "exit": side("AND", [price("<", 1)])},  # unknown indicator
        {"entry": side("AND", [{"left": {"indicator": "price"}, "operator": "~=", "right": {"value": 1}}]), "exit": side("AND", [price("<", 1)])},  # unknown operator
    ],
)
def test_validate_rules_rejects_malformed_trees(rules):
    with pytest.raises(ValueError):
        rule_engine.validate_rules(rules)


# ---------- chart series ----------


def test_build_chart_series_deduplicates_and_assigns_panels():
    rules = {
        "entry": side("AND", [crossing("crosses_above", 20, 50)]),
        "exit": side("OR", [crossing("crosses_below", 20, 50), {"left": {"indicator": "rsi", "period": 14}, "operator": ">", "right": {"value": 70}}]),
    }
    series = rule_engine.build_chart_series(random_walk(60), rules)
    names = sorted(s.name for s in series)
    assert names == ["RSI 14", "SMA 20", "SMA 50"]  # SMA 20/50 appear in both sides but each only once
    panels = {s.name: s.panel for s in series}
    assert panels["SMA 20"] == "price" and panels["RSI 14"] == "osc"


def test_build_chart_series_has_no_series_for_price_or_value_terms():
    rules = {"entry": side("AND", [price(">", 100)]), "exit": side("AND", [price("<", 90)])}
    assert rule_engine.build_chart_series(random_walk(30), rules) == []


# ---------- definition ----------


def test_build_definition_rule_text_reads_naturally():
    rules = {
        "entry": side("AND", [price(">", 100), {"left": {"indicator": "rsi", "period": 14}, "operator": "<", "right": {"value": 70}}]),
        "exit": side("OR", [price("<", 90)]),
    }
    defn = rule_engine.build_definition(rules)
    assert defn.rule_text({}) == "BUY when Price > 100 AND RSI(14) < 70; SELL when Price < 90."
