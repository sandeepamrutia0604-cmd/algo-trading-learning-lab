from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.app.adapters.base import Candle
from backend.app.migrations import ensure_columns
from backend.app.models import Position
from backend.app.services import market_service
from backend.app.services.real_stocks import import_candles
from backend.app.services.seed import ensure_seed_data

WARM = market_service.WARMUP_DAYS  # candles showing when a real stock first appears
QUIET = (100.0, 101.0, 99.0, 100.0)  # open, high, low, close of an ordinary day


@pytest.fixture()
def market(db_session):
    """Seeded market plus the stock XYZ: ordinary days at 100 everywhere except the ones in
    `script` (with at least 2 x WARMUP_DAYS candles, the clock starts on the WARMUP_DAYS-th). XYZ closes at 100 on the market date, so a buy fills at 100. The scripted days
    are numbered 1, 2, 3... from the first day the market will advance to."""

    def build(script=None, total=2 * WARM + 10, skip=()):
        script = script or {}
        ensure_seed_data(db_session)
        candles, day, i = [], date(2025, 9, 1), 0
        while len(candles) < total:
            if day.weekday() < 5:
                k = i - (WARM - 1)  # 0 is the market date, 1 the next day
                i += 1
                if k not in skip:
                    o, h, l, c = script.get(k, QUIET)
                    candles.append(Candle(date=day, open=o, high=h, low=l, close=c, volume=100))
            day += timedelta(days=1)
        import_candles(db_session, "XYZ", "XYZ Ltd", candles, source="csv", replace=False)
        db_session.commit()
        return candles

    return build


def buy(client, quantity=10, **levels):
    return client.post("/api/orders/buy", json={"symbol": "XYZ", "quantity": quantity, **levels})


def position(client):
    return next((p for p in client.get("/api/positions").json() if p["symbol"] == "XYZ"), None)


def advance(client, days=1):
    return client.post("/api/market/advance", json={"days": days}).json()


def trades(client):
    return [t for t in client.get("/api/trades").json() if t["symbol"] == "XYZ"]


# ---------- setting levels on a buy ----------


def test_a_buy_can_set_a_stop_and_a_target_on_the_position(client, market):
    market()
    response = buy(client, stop_loss_price=95, take_profit_price=110)

    assert response.status_code == 200
    held = position(client)
    assert (held["stop_price"], held["target_price"]) == (95.0, 110.0)


def test_a_buy_with_no_levels_leaves_the_position_unprotected(client, market):
    market()
    buy(client)
    assert (position(client)["stop_price"], position(client)["target_price"]) == (None, None)


def test_either_level_can_be_set_alone(client, market):
    market()
    buy(client, stop_loss_price=90)
    assert (position(client)["stop_price"], position(client)["target_price"]) == (90.0, None)


def test_a_stop_at_or_above_the_price_is_refused_and_nothing_is_bought(client, market):
    market()
    cash = client.get("/api/portfolio").json()["cash"]

    response = buy(client, stop_loss_price=100)

    assert response.status_code == 400 and "below the current price" in response.json()["detail"]
    assert position(client) is None and client.get("/api/portfolio").json()["cash"] == cash
    assert trades(client) == []


def test_a_target_at_or_below_the_price_is_refused(client, market):
    market()
    response = buy(client, take_profit_price=99)
    assert response.status_code == 400 and "above the current price" in response.json()["detail"]
    assert position(client) is None


@pytest.mark.parametrize("field", ["stop_loss_price", "take_profit_price"])
@pytest.mark.parametrize("value", [0, -5])
def test_a_zero_or_negative_level_is_rejected_by_validation(client, market, field, value):
    market()
    assert buy(client, **{field: value}).status_code == 422


def test_adding_shares_without_new_levels_keeps_the_ones_already_set(client, market):
    market()
    buy(client, stop_loss_price=95, take_profit_price=110)
    buy(client, quantity=5)

    held = position(client)
    assert held["quantity"] == 15 and (held["stop_price"], held["target_price"]) == (95.0, 110.0)


def test_adding_shares_with_new_levels_replaces_them(client, market):
    market()
    buy(client, stop_loss_price=95, take_profit_price=110)
    buy(client, quantity=5, stop_loss_price=92)

    held = position(client)
    assert (held["stop_price"], held["target_price"]) == (92.0, 110.0)  # only the one given changes


def test_selling_part_of_a_position_keeps_its_levels(client, market):
    market()
    buy(client, stop_loss_price=95, take_profit_price=110)
    client.post("/api/orders/sell", json={"symbol": "XYZ", "quantity": 4})

    held = position(client)
    assert held["quantity"] == 6 and (held["stop_price"], held["target_price"]) == (95.0, 110.0)


def test_selling_everything_clears_them_for_the_next_position(client, market):
    market()
    buy(client, stop_loss_price=95)
    client.post("/api/orders/sell", json={"symbol": "XYZ", "quantity": 10})
    assert position(client) is None

    buy(client)
    assert position(client)["stop_price"] is None


def test_selling_does_not_accept_levels(client, market):
    market()
    buy(client)
    response = client.post("/api/orders/sell", json={"symbol": "XYZ", "quantity": 1, "stop_loss_price": 90})
    assert response.status_code == 200  # a sell has nothing to protect; the extra field is ignored
    assert position(client)["stop_price"] is None


# ---------- editing levels on a position ----------


def test_levels_can_be_set_changed_and_cleared_on_a_held_position(client, market):
    market()
    buy(client)

    body = client.put("/api/positions/XYZ/exits", json={"stop_loss_price": 94, "take_profit_price": 112}).json()
    assert (body["symbol"], body["stop_price"], body["target_price"]) == ("XYZ", 94.0, 112.0)

    body = client.put("/api/positions/xyz/exits", json={"stop_loss_price": 96}).json()
    assert (body["stop_price"], body["target_price"]) == (96.0, None)  # both are replaced: the target was dropped

    body = client.put("/api/positions/XYZ/exits", json={}).json()
    assert (body["stop_price"], body["target_price"]) == (None, None)


def test_editing_levels_checks_them_against_the_current_price(client, market):
    market()
    buy(client)
    assert client.put("/api/positions/XYZ/exits", json={"stop_loss_price": 100}).status_code == 400
    assert client.put("/api/positions/XYZ/exits", json={"take_profit_price": 99}).status_code == 400
    assert position(client)["stop_price"] is None


def test_you_cannot_protect_a_position_you_do_not_hold(client, market):
    market()
    response = client.put("/api/positions/XYZ/exits", json={"stop_loss_price": 95})
    assert response.status_code == 400 and "don't hold" in response.json()["detail"]


def test_an_unknown_symbol_is_a_404(client, market):
    market()
    assert client.put("/api/positions/NOPE/exits", json={"stop_loss_price": 5}).status_code == 404


# ---------- the market reaching a level ----------


def test_a_stop_triggers_when_the_days_low_reaches_it(client, market):
    market({1: (100, 101, 94, 97)})
    buy(client, stop_loss_price=95)

    result = advance(client)

    assert position(client) is None
    assert any("STOP-LOSS" in e and "XYZ" in e for e in result["events"])
    sale = trades(client)[0]  # newest first
    assert (sale["side"], sale["quantity"], sale["price"]) == ("SELL", 10, 95.0)
    assert sale["realized_pnl"] == pytest.approx(-50.0)
    assert sale["reason"] == "Stop-loss at ₹95.00"
    assert sale["source"] == "Manual · stop-loss"
    assert sale["market_date"] == result["date"]  # it is dated the day it happened


def test_a_target_triggers_when_the_days_high_reaches_it(client, market):
    market({1: (100, 111, 100, 108)})
    buy(client, take_profit_price=110)

    result = advance(client)

    assert position(client) is None
    assert any("TAKE-PROFIT" in e for e in result["events"])
    sale = trades(client)[0]
    assert (sale["price"], sale["reason"], sale["source"]) == (110.0, "Take-profit at ₹110.00", "Manual · take-profit")
    assert sale["realized_pnl"] == pytest.approx(100.0)


def test_a_gap_down_through_the_stop_fills_at_the_open_and_says_so(client, market):
    market({1: (90, 93, 88, 91)})
    buy(client, stop_loss_price=95)

    advance(client)

    sale = trades(client)[0]
    assert sale["price"] == 90.0 and sale["realized_pnl"] == pytest.approx(-100.0)
    assert "opened beyond it" in sale["reason"] and "₹90.00" in sale["reason"]


def test_a_gap_up_through_the_target_fills_at_the_open(client, market):
    market({1: (115, 118, 114, 116)})
    buy(client, take_profit_price=110)

    advance(client)

    sale = trades(client)[0]
    assert sale["price"] == 115.0 and sale["realized_pnl"] == pytest.approx(150.0)


def test_a_day_that_reaches_both_levels_takes_the_stop(client, market):
    market({1: (100, 112, 93, 105)})
    buy(client, stop_loss_price=95, take_profit_price=110)

    advance(client)

    assert trades(client)[0]["price"] == 95.0


def test_a_quiet_day_leaves_the_position_and_its_levels_alone(client, market):
    market({1: (100, 104, 97, 101)})
    buy(client, stop_loss_price=95, take_profit_price=110)

    result = advance(client)

    held = position(client)
    assert held["quantity"] == 10 and (held["stop_price"], held["target_price"]) == (95.0, 110.0)
    assert not any("STOP" in e or "TAKE" in e for e in result["events"])


def test_the_whole_position_is_sold_including_shares_added_later(client, market):
    market({1: (100, 101, 90, 92)})
    buy(client, quantity=10, stop_loss_price=95)
    buy(client, quantity=5)

    advance(client)

    assert position(client) is None
    assert trades(client)[0]["quantity"] == 15


def test_several_days_are_checked_one_at_a_time_and_the_exit_happens_on_the_right_day(client, market, db_session):
    candles = market({3: (100, 101, 93, 96)})  # the stop is reached on the third day only
    buy(client, stop_loss_price=95)

    result = advance(client, 5)

    assert position(client) is None
    assert len([t for t in trades(client) if t["side"] == "SELL"]) == 1  # sold once, not on each later day
    assert trades(client)[0]["market_date"] == str(candles[WARM - 1 + 3].date)
    assert result["date"] == str(candles[WARM - 1 + 5].date)  # the clock still went the full five days


def test_a_stock_with_no_candle_that_day_is_skipped_until_it_has_one(client, market):
    # day 1 is missing from XYZ's own data; day 2's candle reaches the stop
    market({2: (100, 101, 93, 96)}, skip={1})
    buy(client, stop_loss_price=95)

    advance(client, 1)
    assert position(client) is not None

    advance(client, 1)
    assert position(client) is None


def test_a_stop_set_after_the_fact_does_not_fire_on_a_day_that_has_already_happened(client, market):
    # the last day of data dipped to 94. Setting a stop at 96 now must not retroactively trigger it
    # when the clock can't move any further.
    last = WARM + 10
    market({last: (100, 101, 94, 99)})
    advance(client, 50)
    advance(client, last - 50)  # to the last day of XYZ's data (a call is limited to 60 days)
    assert advance(client, 1)["reached_end"] is True
    buy(client)
    client.put("/api/positions/XYZ/exits", json={"stop_loss_price": 96})

    result = advance(client, 1)

    assert position(client) is not None
    assert not any("STOP" in e for e in result["events"])


def test_unprotected_positions_advance_as_before(client, market):
    market({1: (100, 101, 50, 60)})
    buy(client)

    result = advance(client, 2)

    assert position(client)["quantity"] == 10
    assert result["events"] == [] or all("STOP" not in e for e in result["events"])


def test_slippage_and_charges_apply_to_an_exit_like_any_other_sale(client, market):
    market({1: (100, 101, 93, 96)})
    client.patch("/api/cost-settings", json={"enabled": True, "slippage_pct": 1.0, "brokerage_pct": 0.1, "brokerage_cap": 0})
    buy(client, stop_loss_price=95)

    advance(client)

    sale = trades(client)[0]
    assert sale["market_price"] == 95.0 and sale["price"] == pytest.approx(94.05)  # 1% worse than the stop
    assert sale["fees"] > 0 and sale["realized_pnl"] < (94.05 - 100) * 10  # the fees come off too


def test_resetting_the_simulation_clears_positions_and_their_levels(client, market, db_session):
    market()
    buy(client, stop_loss_price=95)
    client.post("/api/reset")
    assert db_session.query(Position).count() == 0


# ---------- existing databases ----------


def test_old_position_tables_gain_the_level_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE positions (id INTEGER PRIMARY KEY, stock_id INTEGER, quantity INTEGER, average_price FLOAT)"))
        conn.execute(text("INSERT INTO positions (stock_id, quantity, average_price) VALUES (1, 5, 10.0)"))

    ensure_columns(engine)
    ensure_columns(engine)

    assert {"stop_price", "target_price"} <= {c["name"] for c in inspect(engine).get_columns("positions")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT stop_price, target_price FROM positions")).fetchall() == [(None, None)]
