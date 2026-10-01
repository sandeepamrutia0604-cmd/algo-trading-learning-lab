"""Angel One (SmartAPI) login session: client code + PIN + TOTP in, a JWT session out,
refreshed before it goes stale. Credentials live only in config (.env, never Git -- see
README's Security and Safety Principles) and tokens live only in memory for this process;
neither is ever logged or persisted to the DB.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
import pyotp

BASE_URL = "https://apiconnect.angelone.in"
LOGIN_PATH = "/rest/auth/angelbroking/user/v1/loginByPassword"
REFRESH_PATH = "/rest/auth/angelbroking/jwt/v1/generateTokens"
LOGOUT_PATH = "/rest/secure/angelbroking/user/v1/logout"

# SmartAPI sessions are valid until midnight IST; refresh well before then rather than
# tracking the exact server-side expiry.
REFRESH_AFTER = timedelta(hours=6)


class AngelOneAuthError(Exception):
    """Login/refresh failed. The message is safe to log -- it never includes the PIN, TOTP
    secret, or a token value."""


@dataclass
class AngelOneTokens:
    jwt_token: str
    refresh_token: str
    feed_token: str
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_stale(self) -> bool:
        return datetime.now(timezone.utc) - self.issued_at > REFRESH_AFTER


def _local_mac() -> str:
    node = uuid.getnode()
    return ":".join(f"{(node >> shift) & 0xFF:02x}" for shift in range(40, -1, -8))


def _headers(api_key: str, extra: dict | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1",
        "X-ClientPublicIP": "127.0.0.1",
        "X-MACAddress": _local_mac(),
        "X-PrivateKey": api_key,
    }
    if extra:
        headers.update(extra)
    return headers


def unwrap(response: httpx.Response, action: str) -> dict:
    """SmartAPI's response envelope is {status, message, errorcode, data}; raise with the
    broker's own message rather than a raw HTTP error when status is false."""
    try:
        body = response.json()
    except ValueError:
        raise AngelOneAuthError(f"Angel One {action} returned a non-JSON response (HTTP {response.status_code})") from None
    if not body.get("status"):
        raise AngelOneAuthError(f"Angel One {action} failed: {body.get('message', 'unknown error')} ({body.get('errorcode', '?')})")
    return body["data"]


class AngelOneAuth:
    """Owns the login session for one Angel One account. Construct once and reuse --
    logging in on every request would blow through the 1-request/second login rate limit."""

    def __init__(self, api_key: str, client_code: str, pin: str, totp_secret: str, http: httpx.Client | None = None):
        self.api_key = api_key
        self.client_code = client_code
        self.pin = pin
        self.totp_secret = totp_secret
        self.http = http or httpx.Client(base_url=BASE_URL, timeout=15.0)
        self._tokens: AngelOneTokens | None = None

    def _totp_now(self) -> str:
        return pyotp.TOTP(self.totp_secret).now()

    def login(self) -> AngelOneTokens:
        body = {"clientcode": self.client_code, "password": self.pin, "totp": self._totp_now()}
        response = self.http.post(LOGIN_PATH, json=body, headers=_headers(self.api_key))
        data = unwrap(response, "login")
        self._tokens = AngelOneTokens(jwt_token=data["jwtToken"], refresh_token=data["refreshToken"], feed_token=data["feedToken"])
        return self._tokens

    def tokens(self) -> AngelOneTokens:
        if self._tokens is None:
            return self.login()
        if self._tokens.is_stale:
            self._refresh()
        return self._tokens

    def _refresh(self) -> None:
        assert self._tokens is not None
        headers = _headers(self.api_key, {"Authorization": f"Bearer {self._tokens.jwt_token}"})
        try:
            response = self.http.post(REFRESH_PATH, json={"refreshToken": self._tokens.refresh_token}, headers=headers)
            data = unwrap(response, "token refresh")
        except AngelOneAuthError:
            self.login()  # the refresh token itself expired too -- fall back to a full login
            return
        self._tokens = AngelOneTokens(jwt_token=data["jwtToken"], refresh_token=data["refreshToken"], feed_token=data["feedToken"])

    def auth_headers(self) -> dict:
        """Headers for any authenticated SmartAPI call, logging in or refreshing first if needed."""
        return _headers(self.api_key, {"Authorization": f"Bearer {self.tokens().jwt_token}"})

    def logout(self) -> None:
        if self._tokens is None:
            return
        headers = _headers(self.api_key, {"Authorization": f"Bearer {self._tokens.jwt_token}"})
        self.http.post(LOGOUT_PATH, json={"clientcode": self.client_code}, headers=headers)
        self._tokens = None
