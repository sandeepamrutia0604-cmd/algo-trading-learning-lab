import random
from datetime import datetime, time

import pytest

from backend.app.engine.indicators import bollinger, rsi, sma
from backend.app.models import PriceData, Stock
from backend.app.services import market_service, strategy_service, trading_service
from backend.app.services.exceptions import TradingError
from backend.app.strategies.breakout import BREAKOUT
from backend.app.strategies.combined import COMBINED
from backend.app.strategies.registry import get_definition, list_definitions
from backend.app.strategies.rsi_reversal import RSI_REVERSAL


def random_walk(n=400, seed=3, vol=0.015):
    rng = random.Random(seed)
    closes = [100.0]
    for _ in range(n):
        closes.append(closes[-1] * (1 + rng.gauss(0, vol)))
    return closes


def sides(events):
    return [(e.index, e.side) for e in events]


ALL = [d.key for d in list_definitions()]


# ---------- registry and parameter validation ----------


def test_registry_lists_all_six_strategy_types():
    assert ALL == ["ma_crossover", "rsi", "bollinger", "breakout", "mean_reversion", "combined"]


@pytest.mark.parametrize("key", ALL)
def test_defaults_are_valid_and_rule_text_mentions_both_sides(key):
    defn = get_definition(key)
    params = defn.normalize({})
    assert set(params) == {p.name for p in defn.params}
    rule = defn.rule_text(params)
    assert rule.startswith("BUY when") and "SELL when" in rule
    assert defn.default_name(params, "ALPHA").endswith("on ALPHA")


@pytest.mark.parametrize("key", ALL)
def test_out_of_range_and_unknown_and_non_integer_params_are_rejected(key):
    defn = get_definition(key)
    first = defn.params[0]
    with pytest.raises(ValueError):
        defn.normalize({first.name: first.max + 1})
    with pytest.raises(ValueError):
        defn.normalize({first.name: first.min - 1})
    with pytest.raises(ValueError):
        defn.normalize({"bogus": 1})
    if first.kind == "int":
        with pytest.raises(ValueError):
            defn.normalize({first.name: first.default + 0.5})


@pytest.mark.parametrize(
    "key,params",
    [
        ("ma_crossover", {"fast": 30, "slow": 20}),
        ("rsi", {"oversold": 50, "overbought": 50}),
        ("breakout", {"lookback": 10, "exit_lookback": 20}),
        ("combined", {"fast": 60, "slow": 50}),
    ],
)
def test_cross_field_validation(key, params):
    with pytest.raises(ValueError):
        get_definition(key).normalize(params)


def test_unknown_strategy_type():
    with pytest.raises(ValueError):
        get_definition("moonshot")


# ---------- signal logic, all strategies ----------


@pytest.mark.parametrize("key", ALL)
def test_signals_are_well_formed_and_alternate_starting_with_buy(key):
    defn = get_definition(key)
    events = defn.generate(random_walk(), defn.normalize({}))
    assert events, f"{key} found nothing on 400 days of random data"
    indexes = [e.index for e in events]
    assert indexes == sorted(indexes) and len(set(indexes)) == len(indexes)
    assert [e.side for e in events][0] == "BUY"
    assert all(a.side != b.side for a, b in zip(events, events[1:]))
    assert all(e.headline and e.checks and all(isinstance(c, str) and c for c in e.checks) for e in events)


@pytest.mark.parametrize("key", ALL)
def test_no_look_ahead_signals_on_a_prefix_are_unchanged(key):
    defn = get_definition(key)
    params = defn.normalize({})
    closes = random_walk(300, seed=8)
    full = defn.generate(closes, params)
    for cut in (60, 120, 200, 299):
        partial = defn.generate(closes[:cut], params)
        assert partial == [e for e in full if e.index < cut]


@pytest.mark.parametrize("key", ALL)
def test_chart_series_line_up_with_the_price_history(key):
    defn = get_definition(key)
    closes = random_walk(120)
    series = defn.chart_series(closes, defn.normalize({}))
    assert series
    assert all(len(s.values) == len(closes) for s in series)
    assert all(s.panel in ("price", "osc") for s in series)


# ---------- hand-calculated cases ----------


def test_breakout_matches_hand_calculation():
    # lookback 3, exit 2. Day 3: 6 > highest of [5,5,5] -> BUY.
    # Day 6: 4 < lowest of previous 2 closes [7,6] -> SELL. Day 5: 6 is not below min(6,7).
    params = BREAKOUT.normalize({"lookback": 3, "exit_lookback": 2})
    events = BREAKOUT.generate([5, 5, 5, 6, 7, 6, 4, 3], params)
    assert sides(events) == [(3, "BUY"), (6, "SELL")]
    assert "above the highest close of the previous 3 days (₹5.00)" in events[0].checks[0]


def test_rsi_strategy_matches_hand_calculation():
    # RSI(2) on [10,11,12,11,9,8,9,11,13]: 100, 50, 16.67, 10, 50, 82.0
    # Day 4: 50 -> 16.67 crosses below 30 -> BUY. Day 7: 50 -> 82 crosses above 70 -> SELL.
    closes = [10, 11, 12, 11, 9, 8, 9, 11, 13]
    values = rsi(closes, 2)
    assert values[4] == pytest.approx(100 - 100 / 1.2)
    assert values[7] == pytest.approx(82.0, abs=0.1)

    params = RSI_REVERSAL.normalize({"period": 2, "oversold": 30, "overbought": 70})
    events = RSI_REVERSAL.generate(closes, params)
    assert sides(events) == [(4, "BUY"), (7, "SELL")]
    assert events[0].values["rsi"] == pytest.approx(16.67, abs=0.01)
    assert "oversold line of 30" in events[0].checks[0]


def test_bollinger_signals_satisfy_their_band_conditions():
    defn = get_definition("bollinger")
    params = defn.normalize({})
    closes = random_walk(400, seed=5)
    _, upper, lower = bollinger(closes, params["period"], params["num_std"])
    for e in defn.generate(closes, params):
        i = e.index
        if e.side == "BUY":
            assert closes[i] < lower[i] and closes[i - 1] >= lower[i - 1]
        else:
            assert closes[i] > upper[i] and closes[i - 1] <= upper[i - 1]


def test_mean_reversion_buys_below_threshold_and_sells_back_at_average():
    defn = get_definition("mean_reversion")
    params = defn.normalize({})
    closes = random_walk(400, seed=5)
    middle = sma(closes, params["period"])
    for e in defn.generate(closes, params):
        i = e.index
        if e.side == "BUY":
            assert e.values["z_score"] < -params["entry_z"]
        else:
            assert closes[i] >= middle[i] and closes[i - 1] < middle[i - 1]


# ---------- combined strategy filters ----------

COMBINED_CLOSES = [5, 5, 5, 6, 7, 6, 5, 4]
COMBINED_BASE = {"fast": 2, "slow": 3, "rsi_period": 2, "vol_window": 3}


def test_combined_buys_when_all_filters_pass_and_lists_each_check():
    params = COMBINED.normalize({**COMBINED_BASE, "rsi_max": 100, "max_vol": 20})
    events = COMBINED.generate(COMBINED_CLOSES, params)
    assert sides(events) == [(3, "BUY"), (6, "SELL")]

    buy = events[0]
    assert len(buy.checks) == 4
    assert "crossed above" in buy.checks[0]
    assert "RSI(2)" in buy.checks[1] and "not overbought" in buy.checks[1]
    assert "above the 2-day average" in buy.checks[2]
    assert "Volatility" in buy.checks[3]
    assert "never blocked" in events[1].checks[-1]


def test_combined_rsi_filter_blocks_an_overbought_entry_and_the_later_exit():
    params = COMBINED.normalize({**COMBINED_BASE, "rsi_max": 70, "max_vol": 20})
    # RSI is 100 on the crossover day, so the buy is blocked; the SELL crossover is then ignored (flat)
    assert COMBINED.generate(COMBINED_CLOSES, params) == []


def test_combined_volatility_filter_blocks_an_entry():
    params = COMBINED.normalize({**COMBINED_BASE, "rsi_max": 100, "max_vol": 0.5})
    assert COMBINED.generate(COMBINED_CLOSES, params) == []


# ---------- service and API integration ----------


def set_prices(db, symbol, closes):
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    db.query(PriceData).filter(PriceData.stock_id == stock.id).delete()
    day = market_service.SIM_START_DATE
    for close in closes:
        db.add(
            PriceData(
                stock_id=stock.id,
                timestamp=datetime.combine(day, time.min),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1,
            )
        )
        day = market_service._business_day_after(day)
    stock.current_price = closes[-1]
    db.commit()


def append_price(db, symbol, close):
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    last = (
        db.query(PriceData)
        .filter(PriceData.stock_id == stock.id)
        .order_by(PriceData.timestamp.desc())
        .first()
    )
    day = market_service._business_day_after(last.timestamp.date())
    db.add(
        PriceData(
            stock_id=stock.id,
            timestamp=datetime.combine(day, time.min),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1,
        )
    )
    stock.current_price = close
    db.commit()


def test_strategy_types_endpoint_describes_every_type_and_parameter(client):
    types = client.get("/api/strategy-types").json()
    assert [t["key"] for t in types] == ALL
    rsi_type = next(t for t in types if t["key"] == "rsi")
    assert {p["name"] for p in rsi_type["params"]} == {"period", "oversold", "overbought"}
    assert rsi_type["works_best"] and rsi_type["struggles"] and "{oversold}" in rsi_type["entry_text"]
    period = next(p for p in rsi_type["params"] if p["name"] == "period")
    assert (period["default"], period["min"], period["max"], period["kind"]) == (14, 2, 100, "int")


@pytest.mark.parametrize("key", ALL)
def test_every_type_can_be_created_run_on_history_and_charted(client, key):
    client.post("/api/market/generate", json={"days": 250, "seed": 11})
    created = client.post("/api/strategies", json={"symbol": "ALPHA", "type": key}).json()
    assert created["type"] == key and created["signal_count"] == 0

    signals = client.post(f"/api/strategies/{created['id']}/run").json()
    assert all(s["details"]["checks"] and s["details"]["headline"] and s["reason"] for s in signals)
    assert [s["signal"] for s in reversed(signals)][:1] in ([], ["BUY"])

    series = client.get(f"/api/strategies/{created['id']}/series").json()
    assert series and all(s["points"] for s in series)
    if key in ("rsi", "combined"):
        assert any(s["panel"] == "osc" and s["y_range"] == [0, 100] for s in series)
    if key == "bollinger":
        assert [s["fill_to_previous"] for s in series] == [False, True, False]


def test_series_endpoint_404_for_unknown_strategy(client):
    assert client.get("/api/strategies/999/series").status_code == 404


def test_rsi_strategy_updates_are_validated_against_its_own_rules(client):
    created = client.post("/api/strategies", json={"symbol": "ALPHA", "type": "rsi"}).json()
    bad = client.patch(f"/api/strategies/{created['id']}", json={"params": {"oversold": 60}})
    assert bad.status_code == 400
    good = client.patch(f"/api/strategies/{created['id']}", json={"params": {"oversold": 25}})
    assert good.json()["params"]["oversold"] == 25
    assert good.json()["param_summary"].startswith("RSI period 14 · Oversold below 25")


def test_rsi_strategy_auto_trades_through_the_generic_pipeline(client, db_session):
    set_prices(db_session, "ALPHA", [10, 11, 12, 11])
    created = client.post(
        "/api/strategies",
        json={"symbol": "ALPHA", "type": "rsi", "params": {"period": 2}, "quantity": 7, "auto_trade": True},
    ).json()

    append_price(db_session, "ALPHA", 9)  # RSI(2) drops to 16.67 -> BUY
    events = strategy_service.run_auto_strategies(db_session)
    assert len(events) == 1 and "BUY 7 ALPHA" in events[0]
    assert client.get("/api/positions").json()[0]["quantity"] == 7

    signal = client.get("/api/signals").json()[0]
    assert signal["executed"] is True and signal["details"]["values"]["rsi"] == pytest.approx(16.67, abs=0.01)
    assert client.get(f"/api/strategies/{created['id']}/series").status_code == 200


def test_buy_signal_is_refused_while_the_strategy_already_holds_shares(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5, 6])
    strategy = strategy_service.create_strategy(
        db_session, "ALPHA", {"fast": 2, "slow": 3}, quantity=10, auto_trade=True
    )
    stock = db_session.query(Stock).filter(Stock.symbol == "ALPHA").first()
    trading_service.execute_buy(db_session, "ALPHA", 10, strategy_id=strategy.id)

    day = market_service.latest_market_date(db_session)
    event = get_definition("ma_crossover").generate([5, 5, 5, 6], {"fast": 2, "slow": 3})[0]
    signal = strategy_service._make_signal(strategy, get_definition("ma_crossover"), day, 6.0, event)
    db_session.add(signal)
    db_session.flush()

    with pytest.raises(TradingError, match="already holding"):
        strategy_service._execute_signal(db_session, strategy, stock, signal)
