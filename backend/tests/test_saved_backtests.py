import pytest

from backend.app.models import SavedBacktest
from backend.app.services import cost_service, saved_backtests

RUN = {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 5, "slow": 20}, "quantity": 10, "initial_capital": 100_000}


@pytest.fixture()
def market(client):
    client.post("/api/market/generate", json={"days": 250, "seed": 11})


def save(client, name=None, **change):
    return client.post("/api/backtests/saved", json={"name": name, "request": {**RUN, **change}})


# ---------- saving ----------


def test_saving_stores_the_run_and_returns_its_headline_numbers(client, market):
    live = client.post("/api/backtests/run", json=RUN).json()

    response = save(client, "My first crossover")

    assert response.status_code == 200
    saved = response.json()
    assert saved["name"] == "My first crossover" and saved["symbol"] == "ALPHA" and saved["type_label"] == "MA Crossover"
    for key in ("final_capital", "total_return_pct", "total_trades", "win_rate_pct", "max_drawdown_pct", "period_start", "period_end"):
        assert saved[key] == live[key], key
    assert "result" not in saved and "request" not in saved  # the list stays light


def test_a_blank_name_gets_a_sensible_default_that_mentions_a_partial_period(client, market):
    plain = save(client, "   ").json()
    prices = client.get("/api/stocks/ALPHA/prices?full=true").json()
    windowed = save(client, None, start_date=prices[100]["date"], end_date=prices[200]["date"]).json()

    assert plain["name"] == "MA Crossover on ALPHA"
    assert windowed["name"] == f"MA Crossover on ALPHA ({prices[100]['date']} to {prices[200]['date']})"


def test_the_saved_result_is_exactly_what_a_fresh_run_gives(client, market):
    saved_id = save(client).json()["id"]

    detail = client.get(f"/api/backtests/saved/{saved_id}").json()

    assert detail["result"] == client.post("/api/backtests/run", json=RUN).json()
    assert detail["request"]["params"] == {"fast": 5, "slow": 20}
    assert detail["request"]["start_date"] is None and detail["request"]["initial_capital"] == 100_000


def test_a_custom_rules_run_and_its_dates_can_be_saved_and_read_back(client, market):
    prices = client.get("/api/stocks/ALPHA/prices?full=true").json()
    rules = {
        "entry": {"logic": "AND", "conditions": [{"left": {"indicator": "price"}, "operator": ">", "right": {"value": 100}}]},
        "exit": {"logic": "AND", "conditions": [{"left": {"indicator": "price"}, "operator": "<", "right": {"value": 90}}]},
    }
    body = {"symbol": "ALPHA", "type": "custom", "rules": rules, "quantity": 5, "initial_capital": 50_000, "start_date": prices[50]["date"]}

    response = client.post("/api/backtests/saved", json={"name": "custom", "request": body})

    assert response.status_code == 200, response.text
    detail = client.get(f"/api/backtests/saved/{response.json()['id']}").json()
    assert detail["request"]["rules"] == rules and detail["request"]["start_date"] == prices[50]["date"]


def test_costs_and_risk_flags_are_remembered_as_they_were_when_saved(client, db_session, market):
    cost_service.update_settings(db_session, enabled=True, slippage_pct=0.5, brokerage_pct=0.03, brokerage_cap=20.0, other_charges_pct=0.1)

    saved = save(client).json()
    cost_service.update_settings(db_session, enabled=False)

    assert saved["costs_applied"] is True and saved["risk_managed"] is False
    detail = client.get(f"/api/backtests/saved/{saved['id']}").json()
    assert detail["result"]["costs_applied"] is True and detail["result"]["total_fees"] > 0


def test_a_run_that_fails_is_not_saved(client, market, db_session):
    assert save(client, symbol="NOPE").status_code == 404
    assert save(client, type="not-a-type").status_code == 400
    assert save(client, start_date="2999-01-01").status_code == 400

    assert db_session.query(SavedBacktest).count() == 0


def test_there_is_a_cap_on_how_many_can_be_kept(client, market, monkeypatch):
    monkeypatch.setattr(saved_backtests, "MAX_SAVED", 2)
    assert save(client).status_code == 200 and save(client).status_code == 200

    third = save(client)

    assert third.status_code == 400 and "up to 2" in third.json()["detail"]


# ---------- listing, reading, deleting ----------


def test_the_list_is_newest_first_and_empty_to_begin_with(client, market):
    assert client.get("/api/backtests/saved").json() == []
    first = save(client, "first").json()["id"]
    second = save(client, "second").json()["id"]

    listing = client.get("/api/backtests/saved").json()

    assert [r["id"] for r in listing] == [second, first]
    assert all("result" not in r for r in listing)


def test_listing_does_not_load_the_heavy_result(client, market, db_session):
    save(client)
    db_session.expire_all()

    row = db_session.query(SavedBacktest).one()

    assert "result" not in row.__dict__  # deferred until someone asks for it


def test_deleting_removes_it_and_a_second_delete_is_a_404(client, market):
    saved_id = save(client).json()["id"]

    assert client.delete(f"/api/backtests/saved/{saved_id}").json() == {"deleted": saved_id}
    assert client.get("/api/backtests/saved").json() == []
    assert client.get(f"/api/backtests/saved/{saved_id}").status_code == 404
    assert client.delete(f"/api/backtests/saved/{saved_id}").status_code == 404


def test_an_unknown_id_is_a_clear_404(client):
    response = client.get("/api/backtests/saved/999")

    assert response.status_code == 404 and "doesn't exist" in response.json()["detail"]


def test_a_saved_run_outlives_the_stock_it_was_made_on(client, market):
    client.post("/api/stocks/practice", json={"symbol": "ZETA", "starting_price": 100})
    saved_id = save(client, "zeta run", symbol="ZETA").json()["id"]

    assert client.delete("/api/stocks/ZETA").status_code == 200

    detail = client.get(f"/api/backtests/saved/{saved_id}")
    assert detail.status_code == 200 and detail.json()["symbol"] == "ZETA"
    # re-running it is what fails, with an ordinary message
    assert client.post("/api/backtests/run", json=detail.json()["request"]).status_code == 404


def test_reset_leaves_saved_backtests_alone(client, market):
    save(client)

    client.post("/api/reset")

    assert len(client.get("/api/backtests/saved").json()) == 1
