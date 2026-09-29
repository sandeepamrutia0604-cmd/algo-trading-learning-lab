from datetime import datetime, time

import pytest

from backend.app.models import PriceData, Stock
from backend.app.services import market_service, strategy_service
from backend.app.services.exceptions import InvalidStrategyError


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
    last = db.query(PriceData).filter(PriceData.stock_id == stock.id).order_by(PriceData.timestamp.desc()).first()
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


PRICE_RULES = {
    "entry": {"logic": "AND", "conditions": [{"left": {"indicator": "price"}, "operator": ">", "right": {"value": 100}}]},
    "exit": {"logic": "AND", "conditions": [{"left": {"indicator": "price"}, "operator": "<", "right": {"value": 90}}]},
}


# ---------- service ----------


def test_create_custom_strategy_stores_rules_and_a_readable_description(db_session):
    strategy = strategy_service.create_strategy(
        db_session, "ALPHA", quantity=5, type_key="custom", rules=PRICE_RULES
    )
    assert strategy.type == "custom"
    assert strategy.rules == PRICE_RULES
    assert strategy.description == "BUY when Price > 100; SELL when Price < 90."
    assert strategy.parameters == {"quantity": 5}
    assert strategy.name == "Custom strategy on ALPHA"


def test_create_custom_strategy_rejects_malformed_rules(db_session):
    with pytest.raises(InvalidStrategyError):
        strategy_service.create_strategy(db_session, "ALPHA", type_key="custom", rules={"entry": {}})


def test_update_custom_strategy_replaces_rules_and_description(db_session):
    strategy = strategy_service.create_strategy(db_session, "ALPHA", quantity=5, type_key="custom", rules=PRICE_RULES)
    new_rules = {
        "entry": {"logic": "AND", "conditions": [{"left": {"indicator": "price"}, "operator": ">", "right": {"value": 200}}]},
        "exit": {"logic": "AND", "conditions": [{"left": {"indicator": "price"}, "operator": "<", "right": {"value": 150}}]},
    }
    updated = strategy_service.update_strategy(db_session, strategy.id, quantity=8, rules=new_rules)
    assert updated.rules == new_rules
    assert updated.description == "BUY when Price > 200; SELL when Price < 150."
    assert updated.parameters == {"quantity": 8}


def test_update_custom_strategy_without_rules_keeps_the_existing_ones(db_session):
    strategy = strategy_service.create_strategy(db_session, "ALPHA", quantity=5, type_key="custom", rules=PRICE_RULES)
    updated = strategy_service.update_strategy(db_session, strategy.id, auto_trade=True)
    assert updated.rules == PRICE_RULES
    assert updated.auto_trade is True


def test_strategy_definition_for_custom_type_has_a_custom_label(db_session):
    strategy = strategy_service.create_strategy(db_session, "ALPHA", type_key="custom", rules=PRICE_RULES)
    defn = strategy_service.strategy_definition(strategy)
    assert defn.label == "Custom"
    assert defn.key == "custom"


def test_run_on_history_produces_signals_for_a_custom_strategy(db_session):
    set_prices(db_session, "ALPHA", [80, 110, 95, 80, 130])
    strategy = strategy_service.create_strategy(db_session, "ALPHA", type_key="custom", rules=PRICE_RULES)
    signals = strategy_service.run_on_history(db_session, strategy)
    assert [s.signal for s in sorted(signals, key=lambda s: s.market_date)] == ["BUY", "SELL", "BUY"]


def test_custom_strategy_auto_trades_through_the_generic_pipeline(client, db_session):
    set_prices(db_session, "ALPHA", [80, 80])
    created = client.post(
        "/api/strategies",
        json={"symbol": "ALPHA", "type": "custom", "rules": PRICE_RULES, "quantity": 3, "auto_trade": True},
    ).json()
    assert created["type"] == "custom" and created["rules"] == PRICE_RULES

    append_price(db_session, "ALPHA", 150)  # crosses above the 100 entry threshold
    events = strategy_service.run_auto_strategies(db_session)
    assert len(events) == 1 and "BUY 3 ALPHA" in events[0]
    assert client.get("/api/positions").json()[0]["quantity"] == 3


# ---------- API ----------


def test_create_custom_strategy_via_api(client):
    res = client.post("/api/strategies", json={"symbol": "ALPHA", "type": "custom", "rules": PRICE_RULES})
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "custom" and body["type_label"] == "Custom"
    assert body["rules"] == PRICE_RULES
    assert body["param_summary"] == body["description"]


def test_create_custom_strategy_via_api_rejects_bad_rules(client):
    bad = {"entry": {"logic": "AND", "conditions": []}, "exit": PRICE_RULES["exit"]}
    res = client.post("/api/strategies", json={"symbol": "ALPHA", "type": "custom", "rules": bad})
    assert res.status_code == 400


def test_custom_strategy_run_and_series_endpoints(client):
    rules = {
        "entry": {"logic": "AND", "conditions": [{"left": {"indicator": "sma", "period": 2}, "operator": "crosses_above", "right": {"indicator": "sma", "period": 3}}]},
        "exit": {"logic": "OR", "conditions": [{"left": {"indicator": "rsi", "period": 14}, "operator": ">", "right": {"value": 70}}]},
    }
    client.post("/api/market/generate", json={"days": 200, "seed": 7})
    created = client.post("/api/strategies", json={"symbol": "ALPHA", "type": "custom", "rules": rules}).json()

    signals = client.post(f"/api/strategies/{created['id']}/run").json()
    assert all(s["details"]["checks"] for s in signals)

    series = client.get(f"/api/strategies/{created['id']}/series").json()
    names = sorted(s["name"] for s in series)
    assert names == ["RSI 14", "SMA 2", "SMA 3"]


def test_backtest_endpoint_runs_a_custom_strategy(client):
    client.post("/api/market/generate", json={"days": 150, "seed": 7})
    res = client.post(
        "/api/backtests/run",
        json={"symbol": "ALPHA", "type": "custom", "rules": PRICE_RULES, "quantity": 10, "initial_capital": 100_000},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "custom" and body["rule"] == "BUY when Price > 100; SELL when Price < 90."


def test_backtest_endpoint_requires_rules_for_a_custom_strategy(client):
    client.post("/api/market/generate", json={"days": 60, "seed": 1})
    res = client.post("/api/backtests/run", json={"symbol": "ALPHA", "type": "custom"})
    assert res.status_code == 400
