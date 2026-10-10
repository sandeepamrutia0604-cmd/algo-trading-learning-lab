import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

from backend.app.live import LiveUpdates, is_change, kind_for, origin_allowed


@pytest.fixture()
def market(client):
    client.post("/api/market/generate", json={"days": 80, "seed": 3})


# ---------- which requests count as a change, and what kind ----------


@pytest.mark.parametrize(
    "path, kind",
    [
        ("/api/market/advance", "market"),
        ("/api/market/generate", "market"),
        ("/api/market/config/ALPHA", "market"),
        ("/api/reset", "market"),
        ("/api/orders/buy", "trades"),
        ("/api/orders/sell", "trades"),
        ("/api/stocks/import", "stocks"),
        ("/api/stocks/practice", "stocks"),
        ("/api/stocks/ZETA", "stocks"),
        ("/api/data-sources/import", "stocks"),
        ("/api/risk-settings", "settings"),
        ("/api/cost-settings", "settings"),
        ("/api/strategies", "strategies"),
        ("/api/strategies/3/run", "strategies"),
        ("/api/backtests/saved", "backtests"),
        ("/api/backtests/saved/4", "backtests"),
        ("/api/alerts", "alerts"),
        ("/api/alerts/3/rearm", "alerts"),
        ("/api/backup/restore", "backup"),
        ("/api/portfolio/starting-capital", "other"),
    ],
)
def test_each_path_maps_to_a_kind(path, kind):
    assert kind_for(path) == kind


def test_only_successful_writes_under_api_count_as_changes():
    assert is_change("POST", "/api/orders/buy", 200)
    assert is_change("PUT", "/api/market/config/ALPHA", 200)
    assert is_change("PATCH", "/api/cost-settings", 200)
    assert is_change("DELETE", "/api/stocks/ZETA", 200)
    assert not is_change("GET", "/api/portfolio", 200)  # reading changes nothing
    assert not is_change("POST", "/api/orders/buy", 400)  # a refused order changed nothing
    assert not is_change("POST", "/api/orders/buy", 422)
    assert not is_change("POST", "/api/backtests/run", 200)  # computes, stores nothing
    assert not is_change("POST", "/api/scanner/run", 200)  # a scan reads, stores nothing
    assert not is_change("POST", "/somewhere/else", 200)


# ---------- the socket ----------


def test_a_connected_tab_hears_about_a_change(client, market):
    with client.websocket_connect("/api/ws") as socket:
        client.post("/api/market/advance", json={"days": 1})

        assert socket.receive_json() == {"type": "changed", "kind": "market", "origin": None}


def test_the_message_names_who_made_the_change_so_they_can_skip_the_echo(client, market):
    with client.websocket_connect("/api/ws") as socket:
        client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 1}, headers={"X-Client-Id": "tab-7"})

        assert socket.receive_json() == {"type": "changed", "kind": "trades", "origin": "tab-7"}


def test_every_connected_tab_gets_it(client, market):
    with client.websocket_connect("/api/ws") as first, client.websocket_connect("/api/ws") as second:
        client.post("/api/market/advance", json={"days": 1})

        assert first.receive_json()["kind"] == "market"
        assert second.receive_json()["kind"] == "market"


def test_reads_failures_and_backtest_runs_say_nothing(client, market):
    with client.websocket_connect("/api/ws") as socket:
        client.get("/api/portfolio")
        client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 10**9})  # refused: not enough cash
        client.post("/api/backtests/run", json={"symbol": "ALPHA", "type": "ma_crossover", "quantity": 1, "initial_capital": 1000})
        client.post("/api/market/advance", json={"days": 1})  # the first thing that really changed

        assert socket.receive_json()["kind"] == "market"  # and nothing came before it


def test_saving_and_deleting_a_backtest_are_announced(client, market):
    with client.websocket_connect("/api/ws") as socket:
        saved = client.post("/api/backtests/saved", json={"request": {"symbol": "ALPHA", "type": "ma_crossover", "quantity": 1, "initial_capital": 1000}}).json()
        assert socket.receive_json()["kind"] == "backtests"
        client.delete(f"/api/backtests/saved/{saved['id']}")
        assert socket.receive_json()["kind"] == "backtests"


def test_a_page_from_another_website_is_refused(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws", headers={"origin": "http://evil.example"}):
            pass


def test_a_page_served_by_this_app_is_accepted(client, market):
    with client.websocket_connect("/api/ws", headers={"origin": "http://testserver"}) as socket:
        client.post("/api/market/advance", json={"days": 1})

        assert socket.receive_json()["kind"] == "market"


def test_origin_check_unit():
    class Fake:
        def __init__(self, **headers):
            self.headers = headers

    assert origin_allowed(Fake(host="localhost:8000", origin="http://localhost:8000"))
    assert origin_allowed(Fake(host="localhost:8000"))  # a script, not a browser
    assert not origin_allowed(Fake(host="localhost:8000", origin="https://evil.example"))
    assert not origin_allowed(Fake(host="localhost:8000", origin="http://localhost:9999"))


# ---------- the manager ----------


class FakeSocket:
    def __init__(self, fail=False, stuck=False):
        self.fail, self.stuck, self.received = fail, stuck, []

    async def send_json(self, message):
        if self.stuck:
            await asyncio.sleep(60)
        if self.fail:
            raise RuntimeError("closed")
        self.received.append(message)


def test_a_dead_or_stuck_tab_is_dropped_and_the_rest_still_hear(monkeypatch):
    monkeypatch.setattr("backend.app.live.SEND_TIMEOUT", 0.05)
    live = LiveUpdates()
    good, dead, stuck = FakeSocket(), FakeSocket(fail=True), FakeSocket(stuck=True)
    live._clients.update({good, dead, stuck})

    asyncio.run(live.broadcast({"type": "changed"}))

    assert good.received == [{"type": "changed"}]
    assert live.count == 1


def test_broadcasting_to_nobody_is_fine():
    asyncio.run(LiveUpdates().broadcast({"type": "changed"}))


def test_a_closed_connection_is_forgotten(client):
    from backend.app.live import live

    before = live.count
    with client.websocket_connect("/api/ws"):
        assert live.count == before + 1

    assert live.count == before
