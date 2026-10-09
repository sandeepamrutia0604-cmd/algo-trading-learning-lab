from datetime import date, timedelta

import pytest

from backend.app.adapters.base import Candle
from backend.app.services import market_service
from backend.app.services.real_stocks import import_candles
from backend.app.services.seed import ensure_seed_data

WARM = market_service.WARMUP_DAYS
QUIET = (100.0, 101.0, 99.0, 100.0)  # open, high, low, close of an ordinary day


@pytest.fixture()
def market(db_session):
    """Seeded market plus the stock XYZ: ordinary days at 100 except the ones in `script`, numbered
    1, 2, 3... from the first day the market will advance to (see test_exit_orders.py)."""

    def build(script=None, total=2 * WARM + 10, skip=()):
        script = script or {}
        ensure_seed_data(db_session)
        candles, day, i = [], date(2025, 9, 1), 0
        while len(candles) < total:
            if day.weekday() < 5:
                k = i - (WARM - 1)
                i += 1
                if k not in skip:
                    o, h, l, c = script.get(k, QUIET)
                    candles.append(Candle(date=day, open=o, high=h, low=l, close=c, volume=100))
            day += timedelta(days=1)
        import_candles(db_session, "XYZ", "XYZ Ltd", candles, source="csv", replace=False)
        db_session.commit()

    return build


def make(client, kind="above", level=110, symbol="XYZ", **extra):
    return client.post("/api/alerts", json={"symbol": symbol, "kind": kind, "level": level, **extra})


def advance(client, days=1):
    return client.post("/api/market/advance", json={"days": days}).json()


def alerts(client):
    return client.get("/api/alerts").json()


# ---------- creating, listing, deleting ----------


def test_an_alert_is_created_active_and_listed(client, market):
    market()
    response = make(client, "above", 110, note="breakout?")

    assert response.status_code == 200
    body = response.json()
    assert (body["symbol"], body["kind"], body["level"], body["active"], body["note"]) == ("XYZ", "above", 110.0, True, "breakout?")
    assert [a["id"] for a in alerts(client)] == [body["id"]]


def test_an_alert_that_would_fire_at_once_is_refused(client, market):
    market()
    assert make(client, "above", 100).status_code == 400
    assert make(client, "below", 100).status_code == 400
    assert alerts(client) == []


def test_an_alert_on_an_unknown_stock_is_a_404(client, market):
    market()
    assert make(client, symbol="NOPE").status_code == 404


def test_a_bad_kind_or_level_is_rejected(client, market):
    market()
    assert make(client, kind="sideways").status_code == 422
    assert make(client, level=-5).status_code == 422


def test_an_alert_can_be_deleted(client, market):
    market()
    alert_id = make(client).json()["id"]

    assert client.delete(f"/api/alerts/{alert_id}").status_code == 200
    assert alerts(client) == []
    assert client.delete(f"/api/alerts/{alert_id}").status_code == 404


# ---------- firing as the market advances ----------


def test_an_above_alert_fires_on_the_day_the_high_reaches_it(client, market):
    market({3: (100, 112, 99, 111)})
    alert_id = make(client, "above", 110).json()["id"]

    first = advance(client, 2)
    assert first["events"] == [] and alerts(client)[0]["active"] is True

    third = advance(client, 1)
    assert len(third["events"]) == 1 and third["events"][0].startswith("ALERT: XYZ rose to ₹110.00")
    fired = alerts(client)[0]
    assert (fired["id"], fired["active"], fired["triggered_price"]) == (alert_id, False, 110.0)
    assert fired["triggered_date"] is not None


def test_a_multi_day_advance_still_catches_an_alert_with_no_strategies_or_exits(client, market):
    market({3: (100, 112, 99, 111)})
    make(client, "above", 110)

    result = advance(client, 5)

    assert [e for e in result["events"] if e.startswith("ALERT")]
    assert alerts(client)[0]["active"] is False


def test_a_below_alert_fires_on_the_low(client, market):
    market({2: (100, 101, 94, 96)})
    make(client, "below", 95)

    result = advance(client, 3)

    assert result["events"][0].startswith("ALERT: XYZ fell to ₹95.00")


def test_a_gap_reports_the_open_price(client, market):
    market({2: (120, 125, 118, 122)})
    make(client, "above", 110)

    result = advance(client, 2)

    assert "₹120.00" in result["events"][0] and "opened beyond" in result["events"][0]
    assert alerts(client)[0]["triggered_price"] == 120.0


def test_an_alert_fires_only_once(client, market):
    market({2: (100, 112, 99, 111), 3: (100, 113, 99, 112)})
    make(client, "above", 110)

    assert len(advance(client, 2)["events"]) == 1
    assert advance(client, 1)["events"] == []


def test_a_day_with_no_candle_does_not_fire_the_alert(client, market):
    market({2: (100, 112, 99, 111)}, skip=(2,))  # day 2 is a holiday for this stock
    make(client, "above", 110)

    assert advance(client, 2)["events"] == []
    assert alerts(client)[0]["active"] is True


def test_an_alert_never_trades(client, market):
    market({1: (100, 112, 99, 111)})
    make(client, "above", 110)
    cash = client.get("/api/portfolio").json()["cash"]

    advance(client, 1)

    assert client.get("/api/portfolio").json()["cash"] == cash
    assert client.get("/api/trades").json() == []


# ---------- re-arming and reset ----------


def test_a_fired_alert_can_be_rearmed_once_the_price_is_back_under_it(client, market):
    market({1: (100, 112, 99, 111), 2: (100, 101, 99, 100)})
    alert_id = make(client, "above", 110).json()["id"]
    advance(client, 1)
    # the stock is still at 111 on the market date, so the level is not above the price yet
    assert client.post(f"/api/alerts/{alert_id}/rearm").status_code == 400

    advance(client, 1)  # back to 100
    response = client.post(f"/api/alerts/{alert_id}/rearm")

    assert response.status_code == 200
    body = response.json()
    assert (body["active"], body["triggered_date"], body["triggered_price"]) == (True, None, None)


def test_rearming_an_unknown_alert_is_a_404(client, market):
    market()
    assert client.post("/api/alerts/999/rearm").status_code == 404


def test_reset_clears_the_alerts(client, market):
    market()
    make(client)

    assert client.post("/api/reset").status_code == 200
    assert alerts(client) == []
