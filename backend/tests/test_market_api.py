def test_generate_then_fetch_prices(client):
    res = client.post("/api/market/generate", json={"days": 30, "seed": 1})
    assert res.status_code == 200
    assert res.json()["date"] is not None

    prices = client.get("/api/stocks/ALPHA/prices").json()
    assert len(prices) == 30
    assert set(prices[0]) == {"date", "open", "high", "low", "close", "volume"}

    last_five = client.get("/api/stocks/ALPHA/prices", params={"limit": 5}).json()
    assert last_five == prices[-5:]


def test_advance_extends_history(client):
    client.post("/api/market/generate", json={"days": 10, "seed": 1})
    before = client.get("/api/stocks/BETA/prices").json()

    res = client.post("/api/market/advance", json={"days": 3})
    assert res.status_code == 200

    after = client.get("/api/stocks/BETA/prices").json()
    assert len(after) == 13
    assert after[:10] == before
    assert res.json()["date"] == after[-1]["date"]


def test_stock_current_price_follows_latest_close_and_trades_use_it(client):
    client.post("/api/market/generate", json={"days": 10, "seed": 2})
    last_close = client.get("/api/stocks/ALPHA/prices", params={"limit": 1}).json()[0]["close"]

    stocks = {s["symbol"]: s for s in client.get("/api/stocks").json()}
    assert stocks["ALPHA"]["current_price"] == last_close

    trade = client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 1}).json()
    assert trade["price"] == last_close


def test_config_roundtrip_and_validation(client):
    configs = {c["symbol"]: c for c in client.get("/api/market/config").json()}
    assert configs["BETA"]["model"] == "trending"

    res = client.put(
        "/api/market/config/ALPHA", json={"model": "sideways", "volatility": 0.01, "trend": 0.0}
    )
    assert res.status_code == 200
    assert res.json() == {"symbol": "ALPHA", "model": "sideways", "volatility": 0.01, "trend": 0.0}

    bad_model = client.put(
        "/api/market/config/ALPHA", json={"model": "moonshot", "volatility": 0.01, "trend": 0.0}
    )
    assert bad_model.status_code == 422
    bad_vol = client.put(
        "/api/market/config/ALPHA", json={"model": "sideways", "volatility": 0, "trend": 0.0}
    )
    assert bad_vol.status_code == 422


def test_unknown_symbol_returns_404(client):
    assert client.get("/api/stocks/ZZZZ/prices").status_code == 404
    res = client.put("/api/market/config/ZZZZ", json={"model": "sideways", "volatility": 0.01, "trend": 0.0})
    assert res.status_code == 404


def test_request_bounds_are_enforced(client):
    assert client.post("/api/market/advance", json={"days": 0}).status_code == 422
    assert client.post("/api/market/advance", json={"days": 61}).status_code == 422
    assert client.post("/api/market/generate", json={"days": 1}).status_code == 422


def test_reset_restores_default_history_and_clears_trades(client):
    client.post("/api/market/generate", json={"days": 10, "seed": 2})
    client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 1})

    assert client.post("/api/reset").status_code == 200

    assert client.get("/api/trades").json() == []
    assert len(client.get("/api/stocks/ALPHA/prices").json()) == 60
    assert client.get("/api/portfolio").json()["cash"] == 100000.0
