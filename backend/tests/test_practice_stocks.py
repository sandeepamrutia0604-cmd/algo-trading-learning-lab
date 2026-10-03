import pytest

from backend.app.models import MarketConfig, PriceData, Stock
from backend.app.services import market_service, practice_stocks
from backend.app.services.exceptions import InvalidStockError

NEW = {"symbol": "ZETA", "name": "Zeta Pharma", "starting_price": 320.0, "model": "trending", "volatility": 0.015, "trend": 0.002}


def candle_count(db, symbol):
    stock = db.query(Stock).filter(Stock.symbol == symbol).one()
    return db.query(PriceData).filter(PriceData.stock_id == stock.id).count()


@pytest.fixture()
def market(client):
    client.post("/api/market/generate", json={"days": 80, "seed": 3})


# ---------- creating ----------


def test_a_new_stock_has_history_up_to_the_market_clock_and_its_chosen_behaviour(client, db_session, market):
    response = client.post("/api/stocks/practice", json=NEW)

    assert response.status_code == 200
    body = response.json()
    assert (body["symbol"], body["name"], body["starting_price"], body["source"], body["removable"]) == ("ZETA", "Zeta Pharma", 320.0, "simulated", True)
    # the same number of candles as a built-in stock, ending on the same day
    assert candle_count(db_session, "ZETA") == candle_count(db_session, "ALPHA") == 80
    zeta = client.get("/api/stocks/ZETA/prices").json()
    alpha = client.get("/api/stocks/ALPHA/prices").json()
    assert zeta[0]["date"] == alpha[0]["date"] and zeta[-1]["date"] == alpha[-1]["date"]
    assert body["current_price"] == zeta[-1]["close"]
    config = db_session.query(MarketConfig).join(Stock).filter(Stock.symbol == "ZETA").one()
    assert (config.model, config.volatility, config.trend) == ("trending", 0.015, 0.002)


def test_the_stock_appears_in_the_stock_list_and_market_config(client, market):
    client.post("/api/stocks/practice", json=NEW)

    stocks = {s["symbol"]: s for s in client.get("/api/stocks").json()}
    assert stocks["ZETA"]["removable"] is True and len(stocks["ZETA"]["recent_closes"]) == 30
    assert stocks["ALPHA"]["removable"] is False
    assert any(c["symbol"] == "ZETA" for c in client.get("/api/market/config").json())


def test_symbol_is_uppercased_and_the_name_defaults_sensibly(client, market):
    body = client.post("/api/stocks/practice", json={"symbol": " zeta ", "starting_price": 50}).json()

    assert body["symbol"] == "ZETA" and body["name"] == "ZETA (practice)"


@pytest.mark.parametrize("symbol", ["BAD SYMBOL", "TOOLONGSYMBOL", "A$B", "  "])
def test_an_invalid_symbol_is_refused_with_a_readable_message(client, market, symbol):
    response = client.post("/api/stocks/practice", json={**NEW, "symbol": symbol})

    assert response.status_code == 400
    assert "valid symbol" in response.json()["detail"]


def test_an_existing_symbol_cannot_be_reused(client, market):
    assert client.post("/api/stocks/practice", json=NEW).status_code == 200

    again = client.post("/api/stocks/practice", json=NEW)
    builtin = client.post("/api/stocks/practice", json={**NEW, "symbol": "ALPHA"})

    assert again.status_code == 400 and "already exists" in again.json()["detail"]
    assert builtin.status_code == 400 and "already exists" in builtin.json()["detail"]


@pytest.mark.parametrize(
    "change",
    [{"starting_price": 0}, {"starting_price": -5}, {"volatility": 0}, {"volatility": 0.5}, {"trend": 0.5}, {"model": "magic"}],
)
def test_out_of_range_settings_are_rejected(client, market, change):
    assert client.post("/api/stocks/practice", json={**NEW, **change}).status_code == 422


def test_the_service_itself_rejects_bad_values_and_leaves_nothing_behind(db_session):
    with pytest.raises(InvalidStockError):
        practice_stocks.create(db_session, "ZETA", None, -1, "random_walk", 0.02, 0)
    with pytest.raises(InvalidStockError):
        practice_stocks.create(db_session, "ZETA", None, 10, "nope", 0.02, 0)
    with pytest.raises(InvalidStockError):
        practice_stocks.create(db_session, "ZETA", None, 10, "random_walk", 0, 0)
    assert db_session.query(Stock).filter(Stock.symbol == "ZETA").first() is None


def test_creating_before_any_history_exists_still_gives_a_usable_stock(db_session):
    stock = practice_stocks.create(db_session, "ZETA", None, 100, "random_walk", 0.02, 0, seed=1)

    assert candle_count(db_session, "ZETA") >= market_service.DEFAULT_HISTORY_DAYS
    assert stock.current_price > 0


def test_the_stock_is_deterministic_for_a_seed(db_session):
    first = practice_stocks.create(db_session, "ZETA", None, 100, "volatile", 0.02, 0, seed=7).current_price
    practice_stocks.delete(db_session, "ZETA")
    second = practice_stocks.create(db_session, "ZETA", None, 100, "volatile", 0.02, 0, seed=7).current_price

    assert second == first


# ---------- it behaves like the built-in stocks ----------


def test_the_stock_advances_with_the_market_and_can_be_traded(client, market):
    client.post("/api/stocks/practice", json=NEW)
    before = client.get("/api/stocks/ZETA/prices").json()

    client.post("/api/market/advance", json={"days": 3})
    after = client.get("/api/stocks/ZETA/prices").json()
    assert len(after) == len(before) + 3

    order = client.post("/api/orders/buy", json={"symbol": "ZETA", "quantity": 2})
    assert order.status_code == 200, order.text


def test_regenerate_keeps_the_stock_and_its_behaviour(client, db_session, market):
    client.post("/api/stocks/practice", json=NEW)

    client.post("/api/market/generate", json={"days": 120, "seed": 9})

    assert candle_count(db_session, "ZETA") == 120
    config = db_session.query(MarketConfig).join(Stock).filter(Stock.symbol == "ZETA").one()
    assert config.model == "trending"


def test_reset_keeps_your_stocks_chosen_behaviour_but_restores_the_built_ins(client, db_session, market):
    client.post("/api/stocks/practice", json=NEW)
    client.put("/api/market/config/ALPHA", json={"model": "volatile", "volatility": 0.1, "trend": 0.0})

    assert client.post("/api/reset").status_code == 200

    configs = {c["symbol"]: c for c in client.get("/api/market/config").json()}
    assert configs["ZETA"]["model"] == "trending" and configs["ZETA"]["volatility"] == 0.015
    assert configs["ALPHA"]["model"] == "random_walk" and configs["ALPHA"]["volatility"] == 0.02
    assert candle_count(db_session, "ZETA") == candle_count(db_session, "ALPHA")


def test_a_practice_stock_can_be_backtested(client):
    client.post("/api/market/generate", json={"days": 250, "seed": 4})
    client.post("/api/stocks/practice", json=NEW)

    result = client.post("/api/backtests/run", json={"symbol": "ZETA", "type": "ma_crossover", "quantity": 10, "initial_capital": 100_000})

    assert result.status_code == 200 and len(result.json()["equity_curve"]) == 250


# ---------- deleting ----------


def test_an_unused_practice_stock_can_be_deleted_completely(client, db_session, market):
    client.post("/api/stocks/practice", json=NEW)

    response = client.delete("/api/stocks/zeta")

    assert response.status_code == 200 and response.json() == {"deleted": "ZETA"}
    assert db_session.query(Stock).filter(Stock.symbol == "ZETA").first() is None
    stock_ids = {s.id for s in db_session.query(Stock).all()}
    assert {p.stock_id for p in db_session.query(PriceData).all()} <= stock_ids  # no orphaned candles
    assert {c.stock_id for c in db_session.query(MarketConfig).all()} <= stock_ids
    assert client.get("/api/stocks/ZETA/prices").status_code == 404


def test_built_in_and_imported_stocks_cannot_be_deleted(client, db_session, market):
    assert client.delete("/api/stocks/ALPHA").status_code == 400
    db_session.add(Stock(symbol="REAL", name="Real", source="csv", starting_price=1, current_price=1))
    db_session.commit()

    response = client.delete("/api/stocks/REAL")

    assert response.status_code == 400 and "practice stocks you created" in response.json()["detail"]


def test_deleting_an_unknown_stock_is_a_404(client):
    assert client.delete("/api/stocks/NOPE").status_code == 404


def test_a_stock_you_hold_or_traded_or_built_a_strategy_on_is_kept(client, market):
    client.post("/api/stocks/practice", json=NEW)
    client.post("/api/orders/buy", json={"symbol": "ZETA", "quantity": 2})
    held = client.delete("/api/stocks/ZETA")
    assert held.status_code == 400 and "hold" in held.json()["detail"]

    client.post("/api/orders/sell", json={"symbol": "ZETA", "quantity": 2})
    traded = client.delete("/api/stocks/ZETA")
    assert traded.status_code == 400 and "trades" in traded.json()["detail"]

    client.post("/api/reset")  # clears trades
    client.post("/api/strategies", json={"symbol": "ZETA", "type": "ma_crossover"})
    built = client.delete("/api/stocks/ZETA")
    assert built.status_code == 400 and "strategy" in built.json()["detail"].lower()


def test_after_reset_a_previously_traded_stock_can_be_deleted(client, market):
    client.post("/api/stocks/practice", json=NEW)
    client.post("/api/orders/buy", json={"symbol": "ZETA", "quantity": 2})

    client.post("/api/reset")

    assert client.delete("/api/stocks/ZETA").status_code == 200
