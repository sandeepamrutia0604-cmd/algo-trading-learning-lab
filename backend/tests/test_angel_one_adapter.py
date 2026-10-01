import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.app.adapters.angel_one import HISTORICAL_PATH, LTP_PATH, AngelOneMarketDataAdapter
from backend.app.adapters.angel_one_auth import (
    LOGIN_PATH,
    REFRESH_PATH,
    AngelOneAuth,
    AngelOneAuthError,
    AngelOneTokens,
)
from backend.app.adapters.scrip_master import build_token_map, load_scrip_master
from backend.app.services.exceptions import StockNotFoundError

TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # a well-formed base32 secret; the real value is never ours

LOGIN_RESPONSE = {"status": True, "message": "SUCCESS", "errorcode": "", "data": {"jwtToken": "jwt-1", "refreshToken": "refresh-1", "feedToken": "feed-1"}}
REFRESH_RESPONSE = {"status": True, "message": "SUCCESS", "errorcode": "", "data": {"jwtToken": "jwt-2", "refreshToken": "refresh-2", "feedToken": "feed-2"}}
FAILED_RESPONSE = {"status": False, "message": "Login Id or password is invalid", "errorcode": "AB1000", "data": None}

CANDLE_RESPONSE = {
    "status": True,
    "message": "SUCCESS",
    "errorcode": "",
    "data": [
        ["2025-01-01T00:00:00+05:30", 100.0, 105.0, 99.0, 103.0, 1000],
        ["2025-01-02T00:00:00+05:30", 103.0, 108.0, 102.0, 107.0, 1200],
    ],
}
LTP_RESPONSE = {"status": True, "message": "SUCCESS", "errorcode": "", "data": {"exchange": "NSE", "tradingsymbol": "RELIANCE-EQ", "symboltoken": "2885", "ltp": "104.5"}}

SCRIP_MASTER = [
    {"token": "2885", "symbol": "RELIANCE-EQ", "name": "RELIANCE", "exch_seg": "NSE"},
    {"token": "11536", "symbol": "TCS-EQ", "name": "TCS", "exch_seg": "NSE"},
    {"token": "99926009", "symbol": "NIFTY25JANFUT", "name": "NIFTY", "exch_seg": "NFO"},
]


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://apiconnect.angelone.in")


def json_response(body, status_code=200):
    return httpx.Response(status_code, json=body)


# ---------- auth ----------


def test_login_sends_a_totp_and_stores_the_returned_tokens():
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.path == LOGIN_PATH
        body = json.loads(request.content)
        assert body["clientcode"] == "C123"
        assert body["password"] == "1234"
        assert len(body["totp"]) == 6 and body["totp"].isdigit()
        return json_response(LOGIN_RESPONSE)

    auth = AngelOneAuth("api-key", "C123", "1234", TOTP_SECRET, http=make_client(handler))
    tokens = auth.login()

    assert tokens == AngelOneTokens(jwt_token="jwt-1", refresh_token="refresh-1", feed_token="feed-1", issued_at=tokens.issued_at)
    assert len(seen) == 1
    assert seen[0].headers["X-PrivateKey"] == "api-key"


def test_login_raises_angel_one_auth_error_on_failure():
    auth = AngelOneAuth("api-key", "C123", "1234", TOTP_SECRET, http=make_client(lambda r: json_response(FAILED_RESPONSE)))
    with pytest.raises(AngelOneAuthError, match="invalid"):
        auth.login()


def test_tokens_reuses_an_existing_session_without_logging_in_again():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return json_response(LOGIN_RESPONSE)

    auth = AngelOneAuth("api-key", "C123", "1234", TOTP_SECRET, http=make_client(handler))
    auth.tokens()
    auth.tokens()
    assert calls.count(LOGIN_PATH) == 1


def test_tokens_refreshes_a_stale_session_instead_of_logging_in_again():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return json_response(REFRESH_RESPONSE if request.url.path == REFRESH_PATH else LOGIN_RESPONSE)

    auth = AngelOneAuth("api-key", "C123", "1234", TOTP_SECRET, http=make_client(handler))
    auth._tokens = AngelOneTokens("old-jwt", "old-refresh", "old-feed", issued_at=datetime.now(timezone.utc) - timedelta(hours=7))

    tokens = auth.tokens()
    assert tokens.jwt_token == "jwt-2"
    assert calls == [REFRESH_PATH]


def test_refresh_falls_back_to_a_full_login_when_the_refresh_token_has_expired():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == REFRESH_PATH:
            return json_response(FAILED_RESPONSE)
        return json_response(LOGIN_RESPONSE)

    auth = AngelOneAuth("api-key", "C123", "1234", TOTP_SECRET, http=make_client(handler))
    auth._tokens = AngelOneTokens("old-jwt", "old-refresh", "old-feed", issued_at=datetime.now(timezone.utc) - timedelta(hours=7))

    tokens = auth.tokens()
    assert tokens.jwt_token == "jwt-1"
    assert calls == [REFRESH_PATH, LOGIN_PATH]


def test_logout_clears_the_session():
    auth = AngelOneAuth("api-key", "C123", "1234", TOTP_SECRET, http=make_client(lambda r: json_response(LOGIN_RESPONSE if r.url.path == LOGIN_PATH else {"status": True, "message": "SUCCESS", "errorcode": "", "data": ""})))
    auth.login()
    auth.logout()
    assert auth._tokens is None


# ---------- scrip master ----------


def test_build_token_map_keeps_only_nse_equities_and_strips_the_eq_suffix():
    token_map = build_token_map(SCRIP_MASTER)
    assert token_map == {"RELIANCE": "2885", "TCS": "11536"}


def test_load_scrip_master_caches_to_disk(tmp_path):
    cache_path = tmp_path / "scrip_master.json"
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return json_response(SCRIP_MASTER)

    client = make_client(handler)
    first = load_scrip_master(client, cache_path)
    second = load_scrip_master(client, cache_path)

    assert first == second == SCRIP_MASTER
    assert len(calls) == 1  # second call served from the cache file
    assert cache_path.exists()


# ---------- the adapter itself ----------


def make_adapter(handler, cache_path):
    http = make_client(handler)
    return AngelOneMarketDataAdapter("api-key", "C123", "1234", TOTP_SECRET, scrip_master_cache_path=cache_path, http=http)


def full_handler(request):
    path = request.url.path
    if path == LOGIN_PATH:
        return json_response(LOGIN_RESPONSE)
    if path == HISTORICAL_PATH:
        return json_response(CANDLE_RESPONSE)
    if path == LTP_PATH:
        return json_response(LTP_RESPONSE)
    if request.url.host == "margincalculator.angelone.in":
        return json_response(SCRIP_MASTER)
    return json_response({"status": False, "message": "unexpected path in test", "errorcode": "?", "data": None}, 404)


def test_get_historical_candles_parses_rows_into_candles(tmp_path):
    adapter = make_adapter(full_handler, tmp_path / "scrips.json")
    candles = adapter.get_historical_candles("RELIANCE")
    assert [c.close for c in candles] == [103.0, 107.0]
    assert candles[0].date.isoformat() == "2025-01-01"
    assert candles[0].volume == 1000


def test_get_historical_candles_respects_limit(tmp_path):
    adapter = make_adapter(full_handler, tmp_path / "scrips.json")
    assert len(adapter.get_historical_candles("RELIANCE", limit=1)) == 1


def test_get_historical_candles_is_cached_within_the_ttl(tmp_path):
    calls = []

    def handler(request):
        if request.url.path == HISTORICAL_PATH:
            calls.append(request.url.path)
        return full_handler(request)

    adapter = make_adapter(handler, tmp_path / "scrips.json")
    adapter.get_historical_candles("RELIANCE")
    adapter.get_historical_candles("RELIANCE")
    assert len(calls) == 1


def test_get_latest_price_parses_ltp(tmp_path):
    adapter = make_adapter(full_handler, tmp_path / "scrips.json")
    assert adapter.get_latest_price("RELIANCE") == 104.5


def test_unknown_symbol_raises_stock_not_found(tmp_path):
    adapter = make_adapter(full_handler, tmp_path / "scrips.json")
    with pytest.raises(StockNotFoundError):
        adapter.get_historical_candles("NOTREAL")


def test_resolve_instrument_token(tmp_path):
    adapter = make_adapter(full_handler, tmp_path / "scrips.json")
    assert adapter.resolve_instrument_token("reliance") == "2885"
