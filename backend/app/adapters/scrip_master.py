"""Angel One's published instrument list: a token per tradable symbol, needed because
SmartAPI's data endpoints take instrument tokens, not trading symbols. Downloaded once and
cached to disk (it's regenerated daily on Angel One's side, so last_price in it isn't live --
we only use it for the symbol -> token mapping)."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx

SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
DEFAULT_CACHE_PATH = Path("data/angel_one_scrip_master.json")
DEFAULT_MAX_AGE = timedelta(hours=24)

# exch_seg in the scrip master for NSE's regular cash-market (equity) segment. The docs'
# own example shows "nse_cm", but the live file actually uses plain "NSE" (verified against
# a real download -- RELIANCE-EQ's exch_seg there is "NSE", and "nse_cm" appears nowhere in
# the live data's set of exch_seg values).
NSE_EQUITY_SEGMENT = "NSE"


def load_scrip_master(
    http: httpx.Client, cache_path: Path = DEFAULT_CACHE_PATH, max_age: timedelta = DEFAULT_MAX_AGE
) -> list[dict]:
    if cache_path.exists():
        age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if age < max_age:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    response = http.get(SCRIP_MASTER_URL, timeout=30.0)
    response.raise_for_status()
    rows = response.json()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def build_token_map(scrip_master: list[dict], exch_seg: str = NSE_EQUITY_SEGMENT) -> dict[str, str]:
    """{symbol: token} for one exchange segment, keyed by the bare trading symbol (the
    scrip master's own "RELIANCE-EQ" with its "-EQ" suffix stripped)."""
    token_map: dict[str, str] = {}
    for row in scrip_master:
        if row.get("exch_seg") != exch_seg:
            continue
        symbol = row.get("symbol", "")
        if symbol.endswith("-EQ"):
            token_map[symbol[:-3]] = row["token"]
    return token_map
