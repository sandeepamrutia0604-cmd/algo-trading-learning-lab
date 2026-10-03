"""Live updates: a WebSocket that tells every open browser tab "something changed, reload".

The app is one local user, but it can be open in several tabs (one playing the market while
another watches a chart, say), and until now a tab only learned about its own actions. After any
request that changes state succeeds, `announce_changes` (a middleware in main.py) broadcasts a
small message to every connected tab:

    {"type": "changed", "kind": "market" | "trades" | "stocks" | "settings" | "strategies" |
                                 "backtests" | "other", "origin": "<the X-Client-Id of whoever did it>"}

It carries no data, only the fact that something changed, so a tab simply re-reads what it
shows. `origin` lets the tab that made the change skip the echo (it already refreshed itself).

The socket never accepts a connection from another website: browsers don't apply the
same-origin policy to WebSockets, so without the Origin check any page you had open could
connect to localhost and watch.
"""

import asyncio
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

SEND_TIMEOUT = 2.0  # seconds; a stuck tab must not hold up the others
READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}
# POSTs that compute something but change nothing stored (a backtest, an optimisation, a walk-forward test).
NOT_CHANGES = {"/api/backtests/run", "/api/backtests/optimise", "/api/backtests/walk-forward"}

KINDS = (
    ("/api/market", "market"),
    ("/api/reset", "market"),
    ("/api/orders", "trades"),
    ("/api/stocks", "stocks"),
    ("/api/data-sources", "stocks"),
    ("/api/risk-settings", "settings"),
    ("/api/cost-settings", "settings"),
    ("/api/strategies", "strategies"),
    ("/api/backtests/saved", "backtests"),
)


def kind_for(path: str) -> str:
    for prefix, kind in KINDS:
        if path == prefix or path.startswith(prefix + "/"):
            return kind
    return "other"


def is_change(method: str, path: str, status_code: int) -> bool:
    return (
        method.upper() not in READ_ONLY_METHODS
        and path.startswith("/api/")
        and path not in NOT_CHANGES
        and status_code < 400
    )


def origin_allowed(websocket: WebSocket) -> bool:
    """Same-site pages only. A client with no Origin header (a script, not a browser) is allowed."""
    origin = websocket.headers.get("origin")
    if origin is None:
        return True
    return urlparse(origin).netloc == websocket.headers.get("host")


class LiveUpdates:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    @property
    def count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        clients = list(self._clients)
        if clients:
            await asyncio.gather(*(self._send(client, message) for client in clients))

    async def _send(self, websocket: WebSocket, message: dict) -> None:
        try:
            await asyncio.wait_for(websocket.send_json(message), SEND_TIMEOUT)
        except Exception:  # a closed or stuck tab: forget it, the others still get the message
            self.disconnect(websocket)


live = LiveUpdates()


@router.websocket("/ws")
async def live_socket(websocket: WebSocket) -> None:
    if not origin_allowed(websocket):
        logger.warning("Refused a live-updates connection from origin %s", websocket.headers.get("origin"))
        await websocket.close(code=1008)
        return
    await live.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # nothing is expected; this just notices a disconnect
    except WebSocketDisconnect:
        pass
    finally:
        live.disconnect(websocket)
