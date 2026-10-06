CSV = (
    "Date\tOpen\tHigh\tLow\tClose\tVolume\n"
    "03 Jan 2025\t1,010.0\t1,020.0\t1,000.0\t1,015.0\t3,000\n"
    "02 Jan 2025\t1,000.0\t1,012.0\t995.0\t1,010.0\t2,000\n"
    "01 Jan 2025\t990.0\t1,005.0\t985.0\t1,000.0\t1,000\n"
)


def post(client, **overrides):
    body = {"symbol": "newco", "csv_text": CSV, **overrides}
    return client.post("/api/stocks/import", json=body)


def test_import_creates_a_stock_that_the_rest_of_the_api_serves(client):
    response = post(client, name="New Co")

    assert response.status_code == 200
    summary = response.json()
    quality = summary.pop("data_quality")
    assert summary == {
        "symbol": "NEWCO",
        "name": "New Co",
        "created": True,
        "candles_read": 3,
        "candles_stored": 3,
        "first_date": "2025-01-01",
        "last_date": "2025-01-03",
        "current_price": 1015.0,
        "market_date": "2025-01-03",
    }
    # three days of history is flagged as too short to learn from
    assert (quality["symbol"], quality["candles"], quality["status"], quality["warnings"]) == ("NEWCO", 3, "check", 1)
    assert "NEWCO" in [s["symbol"] for s in client.get("/api/stocks").json()]
    prices = client.get("/api/stocks/NEWCO/prices").json()
    assert [p["close"] for p in prices] == [1000.0, 1010.0, 1015.0]


def test_a_second_import_merges_by_default_and_reports_it_was_not_created(client):
    post(client)
    summary = post(client, csv_text="Date,Open,High,Low,Close,Volume\n2025-01-06,1,2,1,2,5\n").json()

    assert summary["created"] is False
    assert summary["candles_read"] == 1
    assert summary["candles_stored"] == 4


def test_replace_discards_the_old_history(client):
    post(client)
    summary = post(client, csv_text="Date,Open,High,Low,Close,Volume\n2025-01-06,1,2,1,2,5\n", replace=True).json()

    assert summary["candles_stored"] == 1


def test_a_bad_file_is_a_400_with_the_line_number_and_stores_nothing(client):
    response = post(client, csv_text="Date,Open,High,Low,Close\n2025-01-01,1,2,1,oops\n")

    assert response.status_code == 400
    assert "Line 2" in response.json()["detail"]
    assert "NEWCO" not in [s["symbol"] for s in client.get("/api/stocks").json()]


def test_importing_over_a_simulated_stock_is_a_400(client):
    response = post(client, symbol="ALPHA")
    assert response.status_code == 400
    assert "simulated" in response.json()["detail"]


def test_an_invalid_symbol_is_a_400_with_a_readable_message(client):
    for symbol in ("NIFTY 500", "WAYTOOLONGSYMBOL", "bad/slash"):
        response = post(client, symbol=symbol)
        assert response.status_code == 400
        assert "isn't a valid symbol" in response.json()["detail"]
    assert post(client, symbol="").status_code == 422


def test_symbols_with_an_ampersand_or_hyphen_are_fine(client):
    assert post(client, symbol="m&m").json()["symbol"] == "M&M"
    assert post(client, symbol="BAJAJ-AUTO").status_code == 200
