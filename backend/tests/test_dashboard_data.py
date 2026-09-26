import pytest

from backend.app.models.portfolio import INITIAL_VIRTUAL_CASH


def test_stocks_expose_previous_close_and_recent_closes(client):
    client.post("/api/market/generate", json={"days": 40, "seed": 1})
    prices = client.get("/api/stocks/ALPHA/prices").json()
    closes = [p["close"] for p in prices]

    alpha = next(s for s in client.get("/api/stocks").json() if s["symbol"] == "ALPHA")

    assert alpha["recent_closes"] == closes[-30:]
    assert alpha["previous_close"] == closes[-2]
    assert alpha["current_price"] == closes[-1]


def test_stocks_without_history_have_no_previous_close(client):
    alpha = next(s for s in client.get("/api/stocks").json() if s["symbol"] == "ALPHA")
    assert alpha["previous_close"] is None
    assert alpha["recent_closes"] == []


def test_day_pnl_is_quantity_times_change_since_previous_close(client):
    client.post("/api/market/generate", json={"days": 10, "seed": 3})
    client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 10})
    client.post("/api/market/advance", json={"days": 1})

    closes = [p["close"] for p in client.get("/api/stocks/ALPHA/prices").json()]
    expected = 10 * (closes[-1] - closes[-2])

    position = client.get("/api/positions").json()[0]
    assert position["day_pnl"] == pytest.approx(expected)
    assert client.get("/api/portfolio").json()["day_pnl"] == pytest.approx(expected)


def test_day_pnl_is_zero_without_positions(client):
    client.post("/api/market/generate", json={"days": 10, "seed": 3})
    assert client.get("/api/portfolio").json()["day_pnl"] == 0.0


def test_equity_curve_is_flat_without_trades(client):
    client.post("/api/market/generate", json={"days": 15, "seed": 1})
    curve = client.get("/api/portfolio/equity-curve").json()
    assert len(curve) == 15
    assert {p["value"] for p in curve} == {INITIAL_VIRTUAL_CASH}


def test_equity_curve_is_empty_without_price_history(client):
    assert client.get("/api/portfolio/equity-curve").json() == []


def test_equity_curve_replays_trades_and_ends_at_portfolio_value(client):
    client.post("/api/market/generate", json={"days": 10, "seed": 5})
    client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 10})
    client.post("/api/market/advance", json={"days": 3})
    client.post("/api/orders/sell", json={"symbol": "ALPHA", "quantity": 4})
    client.post("/api/market/advance", json={"days": 2})

    curve = client.get("/api/portfolio/equity-curve").json()
    prices = {p["date"]: p["close"] for p in client.get("/api/stocks/ALPHA/prices").json()}
    dates = [p["date"] for p in curve]
    assert len(curve) == 15
    assert dates == sorted(dates)

    buy_price = prices[dates[9]]
    assert curve[8]["value"] == INITIAL_VIRTUAL_CASH  # before the buy
    assert curve[9]["value"] == pytest.approx(INITIAL_VIRTUAL_CASH)  # bought at that day's close

    expected_day_12 = INITIAL_VIRTUAL_CASH - 10 * buy_price + 10 * prices[dates[12]]
    assert curve[12]["value"] == pytest.approx(expected_day_12, abs=0.01)

    summary = client.get("/api/portfolio").json()
    assert curve[-1]["value"] == pytest.approx(summary["portfolio_value"], abs=0.01)
