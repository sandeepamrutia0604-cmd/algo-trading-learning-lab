import gzip
import json
import os
import time
from datetime import date, datetime, timedelta

import httpx
import pytest

import backend.app.adapters as adapters_module
from backend.app.adapters import UpstoxMarketDataAdapter, get_market_data_adapter
from backend.app.adapters.upstox import (
    INSTRUMENTS_URL,
    MAX_DAYS_PER_REQUEST,
    UpstoxError,
    build_instrument_map,
    load_instruments,
)
from backend.app.config import settings
from backend.app.models import PriceData, Stock
from backend.app.services import market_service
from backend.app.services.exceptions import StockNotFoundError
from backend.app.services.real_stocks import import_all_real_stocks

TOKEN = "test-token-not-a-real-one"
RELIANCE_KEY = "NSE_EQ|INE002A01018"

# A slice of the real instruments file: the shapes that matter -- cash equities in the regular
# EQ series, a stock that only trades in BE, and rows (futures, indices) that must be ignored.
INSTRUMENTS = [
    {"segment": "NSE_EQ", "instrument_type": "EQ", "trading_symbol": "RELIANCE", "instrument_key": RELIANCE_KEY, "name": "RELIANCE INDUSTRIES LTD", "isin": "INE002A01018"},
    {"segment": "NSE_EQ", "instrument_type": "EQ", "trading_symbol": "TCS", "instrument_key": "NSE_EQ|INE467B01029", "name": "TATA CONSULTANCY SERV LT"},
    {"segment": "NSE_EQ", "instrument_type": "EQ", "trading_symbol": "M&M", "instrument_key": "NSE_EQ|INE101A01026", "name": "MAHINDRA & MAHINDRA LTD"},
    {"segment": "NSE_EQ", "instrument_type": "BE", "trading_symbol": "TRADEONLY", "instrument_key": "NSE_EQ|INE000000001", "name": "A BE-ONLY STOCK"},
    {"segment": "NSE_EQ", "instrument_type": "BE", "trading_symbol": "BOTH", "instrument_key": "NSE_EQ|INE000000002", "name": "BOTH (BE ROW)"},
    {"segment": "NSE_EQ", "instrument_type": "EQ", "trading_symbol": "BOTH", "instrument_key": "NSE_EQ|INE000000003", "name": "BOTH (EQ ROW)"},
    {"segment": "NSE_EQ", "instrument_type": "SG", "trading_symbol": "GOVBOND", "instrument_key": "NSE_EQ|INE000000004", "name": "A GOVERNMENT SECURITY"},
    {"segment": "NSE_FO", "instrument_type": "FUTSTK", "trading_symbol": "RELIANCE24JANFUT", "instrument_key": "NSE_FO|12345", "name": "RELIANCE"},
    {"segment": "NSE_INDEX", "instrument_type": "INDEX", "trading_symbol": "NIFTY 50", "instrument_key": "NSE_INDEX|Nifty 50", "name": "Nifty 50"},
]

# Candles exactly as the V3 API returns them: [timestamp, open, high, low, close, volume, open interest]
CANDLES = {
    "status": "success",
    "data": {
        "candles": [
            ["2026-10-01T00:00:00+05:30", 1180.1, 1183.9, 1160.8, 1167.7, 16771221, 0],
            ["2026-09-30T00:00:00+05:30", 1182.0, 1196.5, 1181.7, 1187.0, 16376789, 0],
            ["2026-09-29T00:00:00+05:30", 1193.8, 1198.3, 1181.8, 1182.0, 24191416, 0],
        ]
    },
}


def gz(rows) -> bytes:
    return gzip.compress(json.dumps(rows).encode())


def make_adapter(handler, tmp_path, **kwargs):
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.upstox.com")
    return UpstoxMarketDataAdapter(TOKEN, instruments_cache_path=tmp_path / "instruments.json", http=http, **kwargs)


def standard_handler(candles=CANDLES):
    def handler(request):
        if str(request.url) == INSTRUMENTS_URL:
            return httpx.Response(200, content=gz(INSTRUMENTS))
        if "/v3/historical-candle/" in request.url.path:
            return httpx.Response(200, json=candles)
        return httpx.Response(404, json={"status": "error"})

    return handler


# ---------- the instrument file ----------


def test_the_instrument_map_keeps_regular_cash_equities_only():
    mapping = build_instrument_map(INSTRUMENTS)

    assert mapping["RELIANCE"] == RELIANCE_KEY
    assert mapping["TCS"] == "NSE_EQ|INE467B01029"
    assert mapping["M&M"] == "NSE_EQ|INE101A01026"
    assert "RELIANCE24JANFUT" not in mapping and "NIFTY 50" not in mapping and "GOVBOND" not in mapping


def test_a_be_only_stock_is_found_but_the_eq_row_wins_when_both_exist():
    mapping = build_instrument_map(INSTRUMENTS)

    assert mapping["TRADEONLY"] == "NSE_EQ|INE000000001"
    assert mapping["BOTH"] == "NSE_EQ|INE000000003"


def test_instruments_are_downloaded_once_and_cached_to_disk_as_a_small_file(tmp_path):
    cache = tmp_path / "instruments.json"
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=gz(INSTRUMENTS))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    first = load_instruments(client, cache)
    second = load_instruments(client, cache)

    assert first == second and len(calls) == 1 and calls[0] == INSTRUMENTS_URL
    assert {row["segment"] for row in first} == {"NSE_EQ"}  # futures and indices aren't kept
    assert all(row["instrument_type"] in ("EQ", "BE") for row in first)


def test_a_stale_cache_is_downloaded_again(tmp_path):
    cache = tmp_path / "instruments.json"
    cache.write_text("[]", encoding="utf-8")
    two_days_ago = time.time() - 2 * 24 * 3600
    os.utime(cache, (two_days_ago, two_days_ago))

    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=gz(INSTRUMENTS))))

    assert len(load_instruments(client, cache)) > 0


def test_an_already_decompressed_instrument_file_is_accepted(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=json.dumps(INSTRUMENTS).encode())))

    assert any(row["trading_symbol"] == "RELIANCE" for row in load_instruments(client, tmp_path / "i.json"))


# ---------- candles ----------


def test_daily_candles_are_requested_with_the_token_and_the_encoded_instrument_key(tmp_path):
    seen = []

    def handler(request):
        if "/v3/historical-candle/" in request.url.path:
            seen.append(request)
        return standard_handler()(request)

    make_adapter(handler, tmp_path).get_historical_candles("RELIANCE")

    request = seen[0]
    today = date.today()
    expected = f"/v3/historical-candle/NSE_EQ%7CINE002A01018/days/1/{today:%Y-%m-%d}/{today - timedelta(days=5 * 365):%Y-%m-%d}"
    assert request.url.raw_path.decode() == expected
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert request.headers["Accept"] == "application/json"


def test_candles_come_back_oldest_first_even_though_the_api_lists_newest_first(tmp_path):
    candles = make_adapter(standard_handler(), tmp_path).get_historical_candles("RELIANCE")

    assert [c.date for c in candles] == [date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)]
    last = candles[-1]
    assert (last.open, last.high, last.low, last.close, last.volume) == (1180.1, 1183.9, 1160.8, 1167.7, 16771221)


def test_a_repeated_date_is_kept_once(tmp_path):
    doubled = {"status": "success", "data": {"candles": CANDLES["data"]["candles"] + [["2026-10-01T00:00:00+05:30", 1, 2, 1, 2, 5, 0]]}}

    candles = make_adapter(standard_handler(doubled), tmp_path).get_historical_candles("RELIANCE")

    assert len(candles) == 3


def test_limit_returns_the_most_recent_candles(tmp_path):
    candles = make_adapter(standard_handler(), tmp_path).get_historical_candles("RELIANCE", limit=2)

    assert [c.date for c in candles] == [date(2026, 9, 30), date(2026, 10, 1)]


def test_candles_are_cached_briefly(tmp_path):
    calls = []

    def handler(request):
        if "/v3/historical-candle/" in request.url.path:
            calls.append(1)
        return standard_handler()(request)

    adapter = make_adapter(handler, tmp_path)
    adapter.get_historical_candles("RELIANCE")
    adapter.get_historical_candles("reliance")

    assert len(calls) == 1


def test_an_empty_response_is_no_candles_not_an_error(tmp_path):
    empty = {"status": "success", "data": {"candles": []}}

    assert make_adapter(standard_handler(empty), tmp_path).get_historical_candles("RELIANCE") == []


def test_the_history_length_is_capped_at_what_one_request_may_span(tmp_path):
    seen = []

    def handler(request):
        if "/v3/historical-candle/" in request.url.path:
            seen.append(request.url.raw_path.decode())
        return standard_handler()(request)

    make_adapter(handler, tmp_path, history_days=99_999).get_historical_candles("RELIANCE")

    assert seen[0].endswith((date.today() - timedelta(days=MAX_DAYS_PER_REQUEST)).strftime("%Y-%m-%d"))


def test_the_latest_price_is_the_most_recent_close(tmp_path):
    assert make_adapter(standard_handler(), tmp_path).get_latest_price("RELIANCE") == 1167.7


def test_the_latest_price_is_none_when_there_are_no_candles(tmp_path):
    empty = {"status": "success", "data": {"candles": []}}

    assert make_adapter(standard_handler(empty), tmp_path).get_latest_price("RELIANCE") is None


def test_an_unknown_symbol_raises_stock_not_found(tmp_path):
    adapter = make_adapter(standard_handler(), tmp_path)

    with pytest.raises(StockNotFoundError, match="NOTREAL"):
        adapter.get_historical_candles("NOTREAL")


def test_resolve_instrument_key_ignores_case_and_spaces(tmp_path):
    assert make_adapter(standard_handler(), tmp_path).resolve_instrument_key(" reliance ") == RELIANCE_KEY


# ---------- errors and the token ----------


def test_a_rejected_token_gives_a_helpful_message_that_never_contains_the_token(tmp_path):
    def handler(request):
        if str(request.url) == INSTRUMENTS_URL:
            return httpx.Response(200, content=gz(INSTRUMENTS))
        return httpx.Response(401, json={"status": "error", "errors": [{"errorCode": "UDAPI100050", "message": "Invalid token used to access API"}]})

    with pytest.raises(UpstoxError) as error:
        make_adapter(handler, tmp_path).get_historical_candles("RELIANCE")

    message = str(error.value)
    assert "401" in message and "Invalid token used to access API" in message
    assert "generate a new Analytics Token" in message
    assert TOKEN not in message


def test_other_http_errors_are_reported_with_their_status(tmp_path):
    def handler(request):
        if str(request.url) == INSTRUMENTS_URL:
            return httpx.Response(200, content=gz(INSTRUMENTS))
        return httpx.Response(429, text="slow down")

    with pytest.raises(UpstoxError, match="429"):
        make_adapter(handler, tmp_path).get_historical_candles("RELIANCE")


def test_a_non_success_body_is_an_error(tmp_path):
    with pytest.raises(UpstoxError):
        make_adapter(standard_handler({"status": "error", "message": "bad request"}), tmp_path).get_historical_candles("RELIANCE")


@pytest.mark.parametrize("token", ["", "   ", None])
def test_a_missing_token_is_reported_before_any_request(token, tmp_path):
    with pytest.raises(UpstoxError, match="UPSTOX_ANALYTICS_TOKEN"):
        UpstoxMarketDataAdapter(token, instruments_cache_path=tmp_path / "i.json")


# ---------- the factory and the import ----------


def test_factory_selects_upstox_when_configured(db_session):
    original_provider, original_token = settings.market_data_provider, settings.upstox_analytics_token
    settings.market_data_provider, settings.upstox_analytics_token = "upstox", TOKEN
    try:
        assert isinstance(get_market_data_adapter(db_session), UpstoxMarketDataAdapter)
    finally:
        settings.market_data_provider, settings.upstox_analytics_token = original_provider, original_token
        adapters_module._upstox_adapter = None  # don't leak the singleton into other tests


def test_imported_upstox_stocks_are_stored_marked_and_left_alone_by_the_simulator(db_session, tmp_path):
    adapter = make_adapter(standard_handler(), tmp_path)

    [stock] = import_all_real_stocks(db_session, adapter, [{"symbol": "RELIANCE", "name": "Reliance Industries"}], source="upstox")

    assert stock.source == "upstox"
    assert db_session.query(PriceData).filter(PriceData.stock_id == stock.id).count() == 3
    market_service.generate_all(db_session, 20, seed=1)
    market_service.advance(db_session, 5)
    assert db_session.query(PriceData).filter(PriceData.stock_id == stock.id).count() == 3


def test_a_merge_import_keeps_history_the_provider_did_not_return(db_session, tmp_path):
    adapter = make_adapter(standard_handler(), tmp_path)
    import_all_real_stocks(db_session, adapter, [{"symbol": "RELIANCE", "name": "Reliance Industries"}], source="csv")
    stock = db_session.query(Stock).filter(Stock.symbol == "RELIANCE").first()
    db_session.add(PriceData(stock_id=stock.id, timestamp=datetime(2021, 10, 4), open=1, high=2, low=1, close=2, volume=5))
    db_session.commit()

    import_all_real_stocks(db_session, adapter, [{"symbol": "RELIANCE", "name": "Reliance Industries"}], source="upstox", replace=False)

    assert db_session.query(PriceData).filter(PriceData.stock_id == stock.id).count() == 4  # the 2021 row survived
