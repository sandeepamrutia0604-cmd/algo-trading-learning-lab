from datetime import datetime, time

import pytest

from backend.app.models import PriceData, Signal, Stock, Trade
from backend.app.models.portfolio import INITIAL_VIRTUAL_CASH
from backend.app.services import market_service, strategy_service, trading_service


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


def new_strategy(client, **overrides):
    body = {"symbol": "ALPHA", "fast": 2, "slow": 3, "quantity": 10, "auto_trade": False}
    body.update(overrides)
    res = client.post("/api/strategies", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_create_strategy_defaults_and_listing(client):
    created = new_strategy(client)
    assert created["name"] == "MA Crossover 2/3 on ALPHA"
    assert (created["fast"], created["slow"], created["quantity"]) == (2, 3, 10)
    assert created["auto_trade"] is False
    assert created["signal_count"] == 0
    assert "crosses above" in created["description"]
    assert [s["id"] for s in client.get("/api/strategies").json()] == [created["id"]]


@pytest.mark.parametrize(
    "overrides,status",
    [
        ({"fast": 5, "slow": 5}, 422),
        ({"fast": 10, "slow": 5}, 422),
        ({"fast": 1}, 422),
        ({"slow": 501}, 422),
        ({"quantity": 0}, 422),
        ({"symbol": "ZZZZ"}, 404),
    ],
)
def test_create_strategy_validation(client, overrides, status):
    body = {"symbol": "ALPHA", "fast": 2, "slow": 3, "quantity": 10}
    body.update(overrides)
    assert client.post("/api/strategies", json=body).status_code == status


def test_run_on_history_marks_crossovers_with_reasons_and_places_no_trades(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5, 6, 7, 6, 5, 4])
    strategy = new_strategy(client)

    signals = client.post(f"/api/strategies/{strategy['id']}/run").json()

    by_side = {s["signal"]: s for s in signals}
    assert sorted(by_side) == ["BUY", "SELL"]
    buy, sell = by_side["BUY"], by_side["SELL"]
    assert buy["price"] == 6 and sell["price"] == 5
    assert "2-day average" in buy["reason"] and "crossed above" in buy["reason"]
    assert "crossed below" in sell["reason"]
    assert buy["details"]["fast_ma"] == pytest.approx(5.5)
    assert buy["details"]["slow_ma"] == pytest.approx(5.3333, abs=1e-3)
    assert buy["executed"] is False and "no trade" in buy["note"]
    assert client.get("/api/trades").json() == []
    assert client.get("/api/portfolio").json()["cash"] == INITIAL_VIRTUAL_CASH

    listed = client.get("/api/strategies").json()[0]
    assert (listed["signal_count"], listed["buy_count"], listed["sell_count"]) == (2, 1, 1)


def test_run_on_history_is_idempotent_and_replaces_stale_signals(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5, 6, 7, 6, 5, 4])
    strategy = new_strategy(client)
    first = client.post(f"/api/strategies/{strategy['id']}/run").json()
    second = client.post(f"/api/strategies/{strategy['id']}/run").json()
    assert [s["id"] for s in first] == [s["id"] for s in second]

    set_prices(db_session, "ALPHA", [10] * 12)  # flat market: no crossovers any more
    assert client.post(f"/api/strategies/{strategy['id']}/run").json() == []


def test_update_strategy_changes_parameters_and_validates(client):
    strategy = new_strategy(client)
    res = client.patch(f"/api/strategies/{strategy['id']}", json={"fast": 3, "slow": 8, "auto_trade": True})
    body = res.json()
    assert (body["fast"], body["slow"], body["auto_trade"]) == (3, 8, True)
    assert "3-day" in body["description"]

    assert client.patch(f"/api/strategies/{strategy['id']}", json={"fast": 9}).status_code == 400
    assert client.patch("/api/strategies/999", json={"auto_trade": True}).status_code == 404


def test_auto_trade_buys_on_crossover_then_sells_on_reverse_crossover(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5])
    strategy = new_strategy(client, auto_trade=True)

    append_price(db_session, "ALPHA", 6)  # BUY crossover
    events = strategy_service.run_auto_strategies(db_session)
    assert len(events) == 1 and "BUY 10 ALPHA" in events[0]

    position = client.get("/api/positions").json()[0]
    assert (position["symbol"], position["quantity"], position["average_price"]) == ("ALPHA", 10, 6)

    append_price(db_session, "ALPHA", 7)
    append_price(db_session, "ALPHA", 6)
    assert strategy_service.run_auto_strategies(db_session) == []  # no crossover on those days

    append_price(db_session, "ALPHA", 5)  # SELL crossover
    events = strategy_service.run_auto_strategies(db_session)
    assert len(events) == 1 and "SELL 10 ALPHA" in events[0]
    assert client.get("/api/positions").json() == []

    trades = client.get("/api/trades").json()
    assert [t["side"] for t in trades] == ["SELL", "BUY"]
    assert all(t["strategy_id"] == strategy["id"] and t["source"] == strategy["name"] for t in trades)
    assert trades[0]["realized_pnl"] == pytest.approx((5 - 6) * 10)

    signals = client.get("/api/signals").json()
    assert [s["executed"] for s in signals] == [True, True]
    assert signals[0]["trade_quantity"] == 10 and signals[0]["realized_pnl"] == pytest.approx(-10)
    assert client.get("/api/strategies").json()[0]["held"] == 0


def test_auto_trade_off_records_nothing(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5])
    new_strategy(client, auto_trade=False)
    append_price(db_session, "ALPHA", 6)
    assert strategy_service.run_auto_strategies(db_session) == []
    assert client.get("/api/signals").json() == []
    assert client.get("/api/trades").json() == []


def test_signal_is_recorded_but_skipped_when_cash_is_short(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5])
    new_strategy(client, quantity=100000, auto_trade=True)  # 100000 x 6 is more than the cash
    append_price(db_session, "ALPHA", 6)

    events = strategy_service.run_auto_strategies(db_session)

    assert "skipped" in events[0]
    signal = client.get("/api/signals").json()[0]
    assert signal["executed"] is False
    assert signal["note"].startswith("Skipped:") and "cash" in signal["note"]
    assert client.get("/api/trades").json() == []


def test_sell_signal_is_skipped_when_strategy_holds_nothing(client, db_session):
    set_prices(db_session, "ALPHA", [7, 7, 7])
    new_strategy(client, auto_trade=True)
    append_price(db_session, "ALPHA", 6)  # downward cross: SELL with nothing to sell

    events = strategy_service.run_auto_strategies(db_session)

    assert "skipped" in events[0]
    signal = client.get("/api/signals").json()[0]
    assert signal["signal"] == "SELL" and signal["executed"] is False
    assert "no shares" in signal["note"]


def test_sell_only_sells_what_the_strategy_bought(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5])
    new_strategy(client, quantity=10, auto_trade=True)
    trading_service.execute_buy(db_session, "ALPHA", 25)  # manual holding, not the strategy's
    append_price(db_session, "ALPHA", 6)
    strategy_service.run_auto_strategies(db_session)  # strategy buys 10 -> 35 held in total
    for close in (7, 6, 5):
        append_price(db_session, "ALPHA", close)
    strategy_service.run_auto_strategies(db_session)  # SELL signal on the last day

    assert client.get("/api/positions").json()[0]["quantity"] == 25


def test_advance_with_auto_strategy_moves_market_day_by_day(client, db_session):
    client.post("/api/market/generate", json={"days": 20, "seed": 3})
    new_strategy(client, auto_trade=True)

    res = client.post("/api/market/advance", json={"days": 5})

    assert res.status_code == 200
    assert isinstance(res.json()["events"], list)
    assert len(client.get("/api/stocks/ALPHA/prices").json()) == 25


def test_signals_endpoint_filters(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5, 6, 7, 6, 5, 4])
    set_prices(db_session, "BETA", [7, 7, 7, 6, 5])
    a = new_strategy(client, symbol="ALPHA")
    b = new_strategy(client, symbol="BETA")
    client.post(f"/api/strategies/{a['id']}/run")
    client.post(f"/api/strategies/{b['id']}/run")

    assert len(client.get("/api/signals").json()) == 3
    assert len(client.get("/api/signals", params={"strategy_id": a["id"]}).json()) == 2
    assert [s["symbol"] for s in client.get("/api/signals", params={"symbol": "beta"}).json()] == ["BETA"]
    assert len(client.get("/api/signals", params={"limit": 1}).json()) == 1
    assert client.get("/api/signals", params={"symbol": "ZZZZ"}).status_code == 404


def test_delete_strategy_removes_signals_and_detaches_trades(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5])
    strategy = new_strategy(client, auto_trade=True)
    append_price(db_session, "ALPHA", 6)
    strategy_service.run_auto_strategies(db_session)

    assert client.delete(f"/api/strategies/{strategy['id']}").status_code == 200

    assert client.get("/api/strategies").json() == []
    assert client.get("/api/signals").json() == []
    trade = client.get("/api/trades").json()[0]
    assert trade["strategy_id"] is None and trade["source"] == "Manual"
    assert client.delete(f"/api/strategies/{strategy['id']}").status_code == 404


def test_regenerate_clears_only_unexecuted_signals_and_reset_clears_all(client, db_session):
    set_prices(db_session, "ALPHA", [5, 5, 5])
    strategy = new_strategy(client, auto_trade=True)
    append_price(db_session, "ALPHA", 6)
    strategy_service.run_auto_strategies(db_session)  # one executed BUY signal

    alpha = db_session.query(Stock).filter(Stock.symbol == "ALPHA").first()
    db_session.add(
        Signal(
            strategy_id=strategy["id"],
            stock_id=alpha.id,
            market_date=market_service.SIM_START_DATE,
            signal="SELL",
            price=1,
            reason="stale",
            details={},
            executed=False,
        )
    )
    db_session.commit()
    assert len(client.get("/api/signals").json()) == 2

    client.post("/api/market/generate", json={"days": 10, "seed": 1})
    remaining = client.get("/api/signals").json()
    assert [s["executed"] for s in remaining] == [True]

    client.post("/api/reset")
    assert client.get("/api/signals").json() == []
    assert client.get("/api/strategies").json()[0]["id"] == strategy["id"]  # definitions survive
    assert db_session.query(Trade).count() == 0
