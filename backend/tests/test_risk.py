from datetime import datetime, time

import pytest

from backend.app.models import PriceData, Position, Stock
from backend.app.models.portfolio import INITIAL_VIRTUAL_CASH
from backend.app.services import market_service, risk_service, strategy_service, trading_service
from backend.app.services.exceptions import TradingError


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


def enable_risk(db, **overrides):
    return risk_service.update_settings(db, enabled=True, **overrides)


# ---------- settings ----------


def test_default_settings_are_disabled(db_session):
    settings = risk_service.get_settings(db_session)
    assert settings.enabled is False
    assert settings.max_risk_per_trade_pct == 2.0
    assert settings.stop_loss_pct == 5.0
    assert settings.max_open_positions == 5
    assert settings.max_allocation_pct == 20.0


def test_risk_settings_endpoint_round_trips(client):
    defaults = client.get("/api/risk-settings").json()
    assert defaults["enabled"] is False

    updated = client.patch("/api/risk-settings", json={"enabled": True, "stop_loss_pct": 8}).json()
    assert updated["enabled"] is True
    assert updated["stop_loss_pct"] == 8
    assert updated["max_open_positions"] == 5  # untouched fields keep their value


def test_risk_settings_endpoint_validates_ranges(client):
    assert client.patch("/api/risk-settings", json={"stop_loss_pct": 0}).status_code == 422
    assert client.patch("/api/risk-settings", json={"max_open_positions": 0}).status_code == 422
    assert client.patch("/api/risk-settings", json={"max_allocation_pct": 200}).status_code == 422


# ---------- position sizing ----------


def test_position_sizing_matches_the_plan_worked_example(db_session):
    # Capital = 1,00,000, Risk = 2% -> max risk = 2,000; Entry 100 / Stop 95 -> risk/share = 5 -> 400 shares
    enable_risk(db_session, max_risk_per_trade_pct=2, stop_loss_pct=5)
    assert risk_service.portfolio_value(db_session) == INITIAL_VIRTUAL_CASH
    assert risk_service.position_size(db_session, price=100, fallback_qty=999) == 400


def test_position_sizing_falls_back_to_fixed_quantity_when_disabled(db_session):
    assert risk_service.position_size(db_session, price=100, fallback_qty=10) == 10


def test_position_sizing_falls_back_when_not_fully_configured(db_session):
    risk_service.update_settings(db_session, enabled=True, stop_loss_pct=0)
    assert risk_service.position_size(db_session, price=100, fallback_qty=10) == 10


# ---------- hard caps ----------


def test_check_buy_allowed_blocks_a_new_symbol_over_max_open_positions(db_session):
    enable_risk(db_session, max_open_positions=1)
    trading_service.execute_buy(db_session, "ALPHA", 1)  # first position: fine

    beta = db_session.query(Stock).filter(Stock.symbol == "BETA").first()
    with pytest.raises(TradingError, match="open positions"):
        risk_service.check_buy_allowed(db_session, beta, 1, beta.current_price)


def test_check_buy_allowed_permits_adding_to_an_existing_position_at_the_cap(db_session):
    enable_risk(db_session, max_open_positions=1)
    trading_service.execute_buy(db_session, "ALPHA", 1)
    alpha = db_session.query(Stock).filter(Stock.symbol == "ALPHA").first()
    risk_service.check_buy_allowed(db_session, alpha, 1, alpha.current_price)  # no raise


def test_check_buy_allowed_blocks_over_allocation(db_session):
    enable_risk(db_session, max_allocation_pct=10, max_open_positions=50)
    alpha = db_session.query(Stock).filter(Stock.symbol == "ALPHA").first()
    over_budget_qty = int((INITIAL_VIRTUAL_CASH * 0.10) / alpha.current_price) + 5
    with pytest.raises(TradingError, match="allocation"):
        risk_service.check_buy_allowed(db_session, alpha, over_budget_qty, alpha.current_price)


def test_execute_buy_via_api_is_rejected_when_it_breaches_risk_limits(client):
    client.patch("/api/risk-settings", json={"enabled": True, "max_allocation_pct": 1, "max_open_positions": 50})
    res = client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 1000})
    assert res.status_code == 400
    assert "allocation" in res.json()["detail"]


def test_risk_disabled_does_not_block_large_trades(db_session):
    alpha = db_session.query(Stock).filter(Stock.symbol == "ALPHA").first()
    risk_service.check_buy_allowed(db_session, alpha, 1, alpha.current_price)  # no settings enabled -> no raise


# ---------- stop-loss protective exit ----------


def test_stop_loss_price_for_strategy_uses_the_entry_trade(db_session):
    strategy = strategy_service.create_strategy(db_session, "ALPHA", {"fast": 2, "slow": 3}, quantity=10)
    trading_service.execute_buy(db_session, "ALPHA", 10, strategy_id=strategy.id)
    entry_price = db_session.query(Stock).filter(Stock.symbol == "ALPHA").first().current_price

    assert risk_service.stop_loss_price_for_strategy(db_session, strategy.id) is None  # disabled
    enable_risk(db_session, stop_loss_pct=5)
    assert risk_service.stop_loss_price_for_strategy(db_session, strategy.id) == pytest.approx(entry_price * 0.95)


def test_stop_loss_triggers_a_protective_sell_overriding_the_strategy_signal(db_session):
    set_prices(db_session, "ALPHA", [100, 100, 100])
    strategy = strategy_service.create_strategy(db_session, "ALPHA", {"fast": 2, "slow": 3}, quantity=10, auto_trade=True)
    trading_service.execute_buy(db_session, "ALPHA", 10, strategy_id=strategy.id)
    enable_risk(db_session, stop_loss_pct=5)

    append_price(db_session, "ALPHA", 90)  # below the 95 stop
    events = strategy_service.run_auto_strategies(db_session)

    assert len(events) == 1 and "STOP-LOSS SELL 10 ALPHA" in events[0]
    assert strategy_service.strategy_held(db_session, strategy.id) == 0
    position = db_session.query(Position).filter(Position.stock_id == strategy.stock_id).first()
    assert position is None


def test_no_stop_loss_sell_while_price_stays_above_the_stop(db_session):
    # RSI's own exit only fires on a price rise (overbought), so a small dip isolates the stop-loss check.
    set_prices(db_session, "ALPHA", [100, 100, 100])
    strategy = strategy_service.create_strategy(
        db_session, "ALPHA", {"period": 2, "overbought": 95}, quantity=10, auto_trade=True, type_key="rsi"
    )
    trading_service.execute_buy(db_session, "ALPHA", 10, strategy_id=strategy.id)
    enable_risk(db_session, stop_loss_pct=5)

    append_price(db_session, "ALPHA", 96)  # above the 95 stop
    events = strategy_service.run_auto_strategies(db_session)

    assert not any("STOP-LOSS" in e for e in events)
    assert strategy_service.strategy_held(db_session, strategy.id) == 10


# ---------- auto-trade sizing integration ----------


def test_auto_trade_buy_uses_risk_based_sizing_when_enabled(client, db_session):
    enable_risk(db_session, max_risk_per_trade_pct=2, stop_loss_pct=5, max_allocation_pct=100)
    set_prices(db_session, "ALPHA", [10, 11, 12, 11])
    created = client.post(
        "/api/strategies",
        json={"symbol": "ALPHA", "type": "rsi", "params": {"period": 2}, "quantity": 7, "auto_trade": True},
    ).json()

    append_price(db_session, "ALPHA", 9)  # RSI(2) drops -> BUY
    expected_qty = risk_service.position_size(db_session, 9, fallback_qty=7)
    events = strategy_service.run_auto_strategies(db_session)

    assert expected_qty != 7  # sanity: risk sizing actually kicked in, not a no-op
    assert f"BUY {expected_qty} ALPHA" in events[0]
    assert client.get("/api/positions").json()[0]["quantity"] == expected_qty
    assert created["type"] == "rsi"


def test_auto_trade_buy_keeps_fixed_quantity_when_risk_disabled(db_session):
    set_prices(db_session, "ALPHA", [10, 11, 12, 11])
    strategy = strategy_service.create_strategy(
        db_session, "ALPHA", {"period": 2}, quantity=7, auto_trade=True, type_key="rsi"
    )
    append_price(db_session, "ALPHA", 9)
    events = strategy_service.run_auto_strategies(db_session)
    assert "BUY 7 ALPHA" in events[0]


# ---------- sizing that fits the allocation cap ----------


def test_position_size_can_fit_the_allocation_cap(db_session):
    # 2% risk / 5% stop wants 400 shares at 100 (40% of 1,00,000); the default 20% cap allows 200.
    enable_risk(db_session, max_risk_per_trade_pct=2, stop_loss_pct=5)
    assert risk_service.position_size(db_session, price=100, fallback_qty=999) == 400
    assert risk_service.position_size(db_session, price=100, fallback_qty=999, fit_allocation_cap=True) == 200


def test_position_size_fitted_to_the_cap_passes_the_allocation_check(db_session):
    enable_risk(db_session, max_risk_per_trade_pct=2, stop_loss_pct=5, max_open_positions=50)
    alpha = db_session.query(Stock).filter(Stock.symbol == "ALPHA").first()
    quantity = risk_service.position_size(db_session, alpha.current_price, 1, fit_allocation_cap=True)

    assert quantity > 0
    risk_service.check_buy_allowed(db_session, alpha, quantity, alpha.current_price)  # no raise
