import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from backend.app.adapters.base import Candle, MarketDataAdapter
from backend.app.adapters.upstox import UpstoxError, UpstoxMarketDataAdapter
from backend.app.models import PriceData, Stock
from backend.app.services import data_sources
from backend.app.services.exceptions import StockNotFoundError

SECRET = "super-secret-token-value"


def settings(**overrides):
    values = {
        "upstox_analytics_token": "",
        "angel_one_api_key": "",
        "angel_one_client_code": "",
        "angel_one_pin": "",
        "angel_one_totp_secret": "",
    }
    return SimpleNamespace(**{**values, **overrides})


@pytest.fixture()
def configured(monkeypatch):
    def apply(**overrides):
        monkeypatch.setattr(data_sources, "current_settings", lambda: settings(**overrides))

    return apply


def candles(days: int, base: float = 100.0) -> list[Candle]:
    return [Candle(date=date(2025, 1, d), open=base + d, high=base + d + 1, low=base + d - 1, close=base + d, volume=10) for d in range(1, days + 1)]


class FakeBroker(MarketDataAdapter):
    """Knows some symbols; raises what a real adapter would for others."""

    def __init__(self, known=("WIPRO", "SBIN", "RELIANCE", "TCS"), fail_with=None):
        self.known, self.fail_with, self.asked = set(known), fail_with or {}, []

    def get_historical_candles(self, symbol, limit=None):
        self.asked.append(symbol)
        if symbol in self.fail_with:
            raise self.fail_with[symbol]
        if symbol not in self.known:
            raise StockNotFoundError(f"Unknown NSE equity symbol: {symbol}")
        return candles(5)

    def get_latest_price(self, symbol):
        return 100.0

    def instrument_name(self, symbol):
        return {"WIPRO": "Wipro Ltd", "SBIN": "State Bank Of India"}.get(symbol)


# ---------- which sources are set up ----------


def test_nothing_is_configured_until_the_env_values_are_present(configured):
    configured()

    status = {s["key"]: s for s in data_sources.source_status()}

    assert status["upstox"]["configured"] is False
    assert status["upstox"]["missing"] == ["UPSTOX_ANALYTICS_TOKEN"]
    assert status["angel_one"]["missing"] == ["ANGEL_ONE_API_KEY", "ANGEL_ONE_CLIENT_CODE", "ANGEL_ONE_PIN", "ANGEL_ONE_TOTP_SECRET"]


def test_a_source_is_configured_once_all_its_values_exist(configured):
    configured(upstox_analytics_token=SECRET, angel_one_api_key="a", angel_one_client_code="b", angel_one_pin="c")

    status = {s["key"]: s for s in data_sources.source_status()}

    assert status["upstox"]["configured"] is True and status["upstox"]["missing"] == []
    assert status["angel_one"]["configured"] is False and status["angel_one"]["missing"] == ["ANGEL_ONE_TOTP_SECRET"]


def test_the_status_never_contains_a_credential_value(configured):
    configured(upstox_analytics_token=SECRET, angel_one_pin="1234")

    assert SECRET not in json.dumps(data_sources.source_status())
    assert "1234" not in json.dumps(data_sources.source_status())


def test_opening_an_unconfigured_source_names_what_to_add(configured):
    configured()

    with pytest.raises(data_sources.SourceNotConfigured, match="UPSTOX_ANALYTICS_TOKEN"):
        data_sources.open_adapter("upstox")


def test_upstox_opens_with_five_years_by_default_and_honours_years(configured):
    configured(upstox_analytics_token=SECRET)

    default, _ = data_sources.open_adapter("upstox")
    chosen, _ = data_sources.open_adapter("upstox", 8)

    assert isinstance(default, UpstoxMarketDataAdapter)
    assert default.history_days == 5 * 365 and chosen.history_days == 8 * 365


# ---------- importing a list of symbols ----------


def test_each_symbol_is_imported_and_a_bad_one_does_not_stop_the_rest(db_session):
    outcomes = data_sources.import_symbols(db_session, FakeBroker(), ["WIPRO", "NOSUCHCO", "SBIN"], source="upstox")

    assert [(o.symbol, o.ok) for o in outcomes] == [("WIPRO", True), ("NOSUCHCO", False), ("SBIN", True)]
    assert "Unknown NSE equity symbol" in outcomes[1].error
    stored = {s.symbol: s for s in db_session.query(Stock).filter(Stock.symbol.in_(["WIPRO", "NOSUCHCO", "SBIN"]))}
    assert set(stored) == {"WIPRO", "SBIN"}  # the failed one left no stray row
    assert all(s.source == "upstox" for s in stored.values())


def test_a_successful_outcome_reports_what_was_stored(db_session):
    [outcome] = data_sources.import_symbols(db_session, FakeBroker(), ["WIPRO"], source="angel_one")

    assert (outcome.candles, outcome.first_date, outcome.last_date) == (5, date(2025, 1, 1), date(2025, 1, 5))
    assert outcome.current_price == 105.0


def test_new_stocks_get_the_brokers_company_name_known_ones_keep_theirs(db_session):
    outcomes = data_sources.import_symbols(db_session, FakeBroker(), ["WIPRO", "RELIANCE"], source="upstox")

    assert outcomes[0].name == "Wipro Ltd"
    assert outcomes[1].name == "Reliance Industries"  # from the curated list, not the broker


def test_an_existing_stock_is_never_renamed_from_the_broker_list(db_session):
    db_session.add(Stock(symbol="SBIN", name="My own name", source="csv", starting_price=1, current_price=1))
    db_session.commit()

    [outcome] = data_sources.import_symbols(db_session, FakeBroker(), ["SBIN"], source="upstox")

    assert outcome.name == "My own name"


def test_replace_swaps_the_history_and_merge_keeps_what_the_broker_lacks(db_session):
    stock = Stock(symbol="WIPRO", name="Wipro", source="csv", starting_price=1, current_price=1)
    db_session.add(stock)
    db_session.flush()
    db_session.add(PriceData(stock_id=stock.id, timestamp=datetime(2020, 6, 1), open=1, high=2, low=1, close=2, volume=5))
    db_session.commit()

    data_sources.import_symbols(db_session, FakeBroker(), ["WIPRO"], source="upstox", merge=True)
    assert db_session.query(PriceData).filter(PriceData.stock_id == stock.id).count() == 6  # 2020 row kept

    data_sources.import_symbols(db_session, FakeBroker(), ["WIPRO"], source="upstox", merge=False)
    assert db_session.query(PriceData).filter(PriceData.stock_id == stock.id).count() == 5  # replaced


def test_a_rejected_token_stops_the_batch_instead_of_failing_every_symbol_alike(db_session):
    broker = FakeBroker(fail_with={"SBIN": UpstoxError("Upstox returned HTTP 401", auth_failed=True)})

    outcomes = data_sources.import_symbols(db_session, broker, ["WIPRO", "SBIN", "TCS"], source="upstox")

    assert [o.ok for o in outcomes] == [True, False, False]
    assert "401" in outcomes[1].error
    assert "Not tried" in outcomes[2].error
    assert broker.asked == ["WIPRO", "SBIN"]  # TCS was never requested


def test_an_ordinary_error_does_not_stop_the_batch(db_session):
    broker = FakeBroker(fail_with={"SBIN": UpstoxError("Upstox returned HTTP 429: slow down")})

    outcomes = data_sources.import_symbols(db_session, broker, ["SBIN", "WIPRO"], source="upstox")

    assert [o.ok for o in outcomes] == [False, True]


def test_an_invalid_symbol_is_reported_not_raised(db_session):
    broker = FakeBroker(known=("BAD SYMBOL",))

    [outcome] = data_sources.import_symbols(db_session, broker, ["BAD SYMBOL"], source="upstox")

    assert outcome.ok is False and "isn't a valid symbol" in outcome.error


# ---------- the API ----------


class Closer:
    def __init__(self):
        self.closed = 0

    def __call__(self):
        self.closed += 1


@pytest.fixture()
def fake_open(monkeypatch):
    closer, broker = Closer(), FakeBroker()
    seen = {}

    def open_adapter(source, years=None):
        seen.update(source=source, years=years)
        return broker, closer

    monkeypatch.setattr(data_sources, "open_adapter", open_adapter)
    return SimpleNamespace(closer=closer, broker=broker, seen=seen)


def test_api_lists_the_sources_and_what_each_still_needs(client, configured):
    configured(upstox_analytics_token=SECRET)

    response = client.get("/api/data-sources")

    assert response.status_code == 200
    sources = {s["key"]: s for s in response.json()}
    assert sources["upstox"]["configured"] is True
    assert "ANGEL_ONE_PIN" in sources["angel_one"]["missing"]
    assert SECRET not in response.text


def test_api_imports_symbols_from_a_broker_and_stores_them(client, fake_open):
    body = {"source": "upstox", "symbols": ["wipro", "NOSUCHCO", "SBIN"], "years": 8, "merge": False}

    result = client.post("/api/data-sources/import", json=body).json()

    assert (result["source"], result["imported"], result["failed"]) == ("upstox", 2, 1)
    assert [(r["symbol"], r["ok"]) for r in result["results"]] == [("WIPRO", True), ("NOSUCHCO", False), ("SBIN", True)]
    assert result["results"][0]["name"] == "Wipro Ltd" and result["results"][0]["candles_stored"] == 5
    assert "Unknown NSE equity symbol" in result["results"][1]["error"]
    assert result["market_date"] is not None
    assert fake_open.seen == {"source": "upstox", "years": 8}
    assert {"WIPRO", "SBIN"} <= {s["symbol"] for s in client.get("/api/stocks").json()}


def test_api_always_closes_the_broker_session(client, fake_open):
    client.post("/api/data-sources/import", json={"source": "upstox", "symbols": ["WIPRO"]})
    assert fake_open.closer.closed == 1


def test_api_ignores_duplicate_and_blank_symbols(client, fake_open):
    result = client.post("/api/data-sources/import", json={"source": "upstox", "symbols": ["wipro", "WIPRO", "  ", " sbin "]}).json()

    assert [r["symbol"] for r in result["results"]] == ["WIPRO", "SBIN"]
    assert fake_open.broker.asked == ["WIPRO", "SBIN"]


def test_api_reports_what_to_add_when_a_source_is_not_set_up(client, configured):
    configured()

    response = client.post("/api/data-sources/import", json={"source": "upstox", "symbols": ["WIPRO"]})

    assert response.status_code == 400
    assert "UPSTOX_ANALYTICS_TOKEN" in response.json()["detail"]


def test_api_rejects_years_for_angel_one(client, fake_open):
    response = client.post("/api/data-sources/import", json={"source": "angel_one", "symbols": ["WIPRO"], "years": 3})

    assert response.status_code == 400
    assert fake_open.seen == {}  # refused before anything was opened


@pytest.mark.parametrize(
    "body",
    [
        {"source": "zerodha", "symbols": ["WIPRO"]},
        {"source": "upstox", "symbols": []},
        {"source": "upstox", "symbols": ["A"] * 26},
        {"source": "upstox", "symbols": ["WIPRO"], "years": 11},
        {"source": "upstox", "symbols": ["WIPRO"], "years": 0},
    ],
)
def test_api_validates_the_request(client, fake_open, body):
    assert client.post("/api/data-sources/import", json=body).status_code == 422


def test_api_with_only_blank_symbols_is_a_400(client, fake_open):
    assert client.post("/api/data-sources/import", json={"source": "upstox", "symbols": ["  ", ""]}).status_code == 400


def test_api_import_includes_a_data_check_for_each_imported_stock(client, fake_open):
    result = client.post("/api/data-sources/import", json={"source": "upstox", "symbols": ["WIPRO", "NOSUCHCO"]}).json()

    imported, failed = result["results"]
    # five days of history is too short to learn much from, which the check says
    assert (imported["data_quality"]["symbol"], imported["data_quality"]["candles"]) == ("WIPRO", 5)
    assert (imported["data_quality"]["status"], imported["data_quality"]["warnings"]) == ("check", 1)
    assert failed["data_quality"] is None
