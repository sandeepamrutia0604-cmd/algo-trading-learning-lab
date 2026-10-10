import pytest

from backend.app.live import is_change, kind_for
from backend.app.models import SavedPortfolioBacktest
from backend.app.services import portfolio_backtest_service, saved_portfolio_backtests

RUN = {"symbols": ["ALPHA", "BETA", "GAMMA"], "type": "ma_crossover", "params": {"fast": 5, "slow": 20}, "quantity": 10, "initial_capital": 100_000}


@pytest.fixture()
def market(client):
    client.post("/api/market/generate", json={"days": 250, "seed": 11})


def run(client, **change):
    return client.post("/api/portfolio-backtests/run", json={**RUN, **change})


# ---------- running ----------


def test_a_run_returns_the_account_the_baseline_the_per_stock_rows_and_symbol_tagged_trades(client, market):
    r = run(client)
    assert r.status_code == 200
    out = r.json()
    assert out["symbols"] == ["ALPHA", "BETA", "GAMMA"] and out["type_label"] == "MA Crossover"
    assert len(out["baseline_curve"]) == len(out["equity_curve"]) > 100
    assert out["baseline_curve"][0]["value"] == pytest.approx(100_000, rel=0.05)
    assert out["total_trades"] > 0 and {t["symbol"] for t in out["trades"]} <= set(out["symbols"])
    assert out["metrics"]["buy_hold"] is not None and 0 <= out["metrics"]["exposure_pct"] <= 100
    assert set(out["skipped_by_reason"]) == {"cash", "allocation", "max_positions", "size"}
    assert out["skipped_buys"] == sum(out["skipped_by_reason"].values())


def test_the_per_stock_rows_add_up_to_the_accounts_total_profit(client, market):
    out = run(client).json()
    total_pnl = out["final_capital"] - out["initial_capital"]
    assert sum(s["total_pnl"] for s in out["per_stock"]) == pytest.approx(total_pnl, abs=1.0)
    assert sum(s["contribution_pct"] for s in out["per_stock"]) == pytest.approx(out["total_return_pct"], abs=0.01)
    assert sum(s["trades"] for s in out["per_stock"]) == out["total_trades"]


def test_equity_is_never_more_than_the_money_can_explain(client, market):
    out = run(client, fill_mode="next_open", stop_loss_pct=5, take_profit_pct=10).json()
    assert out["fill_mode"] == "next_open" and out["stop_loss_pct"] == 5
    assert all(p["value"] > 0 for p in out["equity_curve"])


def test_the_symbol_order_and_case_do_not_matter_and_repeats_are_dropped(client, market):
    a = run(client, symbols=["gamma", "ALPHA", "beta", "alpha"]).json()
    b = run(client).json()
    assert a["symbols"] == ["ALPHA", "BETA", "GAMMA"] and a["equity_curve"] == b["equity_curve"]


def test_risk_limits_show_up_when_risk_management_is_on(client, market):
    client.patch("/api/risk-settings", json={"enabled": True, "max_risk_per_trade_pct": 2, "stop_loss_pct": 5, "max_open_positions": 1, "max_allocation_pct": 50})
    out = run(client).json()
    assert out["risk_managed"] and out["max_open_positions"] == 1 and out["peak_positions"] <= 1


@pytest.mark.parametrize("change", [
    {"symbols": ["ALPHA"]},
    {"symbols": ["ALPHA", "ALPHA"]},
    {"symbols": [f"S{i}" for i in range(21)]},
])
def test_too_few_or_too_many_stocks_are_refused(client, market, change):
    assert run(client, **change).status_code in (400, 422)


def test_an_unknown_stock_and_bad_dates_are_refused_with_a_message(client, market):
    r = run(client, symbols=["ALPHA", "NOPE"])
    assert r.status_code == 404 or r.status_code == 400
    assert "NOPE" in r.json()["detail"]
    assert run(client, start_date="2025-06-01", end_date="2025-01-01").status_code == 422
    r = run(client, start_date="2090-01-01")
    assert r.status_code == 400 and "ALPHA" in r.json()["detail"]


def test_running_does_not_announce_a_change_to_other_tabs():
    assert not is_change("POST", "/api/portfolio-backtests/run", 200)
    assert is_change("POST", "/api/portfolio-backtests/saved", 200)
    assert kind_for("/api/portfolio-backtests/saved/3") == "backtests"


def test_the_service_refuses_a_zero_quantity(db_session):
    with pytest.raises(Exception):
        portfolio_backtest_service.run(db_session, ["ALPHA", "BETA"], "ma_crossover", {}, 0, 1000)


# ---------- saving ----------


def test_saving_stores_the_run_and_the_result_matches_a_fresh_run(client, market):
    saved = client.post("/api/portfolio-backtests/saved", json={"name": "Three stocks", "request": RUN}).json()
    assert saved["name"] == "Three stocks" and saved["symbols"] == ["ALPHA", "BETA", "GAMMA"]
    assert "result" not in saved
    detail = client.get(f"/api/portfolio-backtests/saved/{saved['id']}").json()
    assert detail["result"] == run(client).json()
    assert detail["request"]["symbols"] == RUN["symbols"]
    assert client.get("/api/portfolio-backtests/saved").json()[0]["id"] == saved["id"]


def test_a_blank_name_gets_a_default(client, market):
    saved = client.post("/api/portfolio-backtests/saved", json={"name": "  ", "request": RUN}).json()
    assert saved["name"] == "MA Crossover on 3 stocks (ALPHA, BETA, GAMMA)"


def test_a_saved_run_can_be_deleted_and_a_missing_one_is_a_404(client, market):
    saved_id = client.post("/api/portfolio-backtests/saved", json={"request": RUN}).json()["id"]
    assert client.delete(f"/api/portfolio-backtests/saved/{saved_id}").json() == {"deleted": saved_id}
    assert client.get(f"/api/portfolio-backtests/saved/{saved_id}").status_code == 404
    assert client.delete(f"/api/portfolio-backtests/saved/{saved_id}").status_code == 404


def test_saving_stops_at_the_cap(client, market, db_session, monkeypatch):
    monkeypatch.setattr(saved_portfolio_backtests, "MAX_SAVED", 1)
    assert client.post("/api/portfolio-backtests/saved", json={"request": RUN}).status_code == 200
    r = client.post("/api/portfolio-backtests/saved", json={"request": RUN})
    assert r.status_code == 400 and "1 saved" in r.json()["detail"]
    assert db_session.query(SavedPortfolioBacktest).count() == 1


def test_listing_does_not_load_the_big_result(client, market, db_session):
    client.post("/api/portfolio-backtests/saved", json={"request": RUN})
    db_session.expire_all()
    row = saved_portfolio_backtests.list_all(db_session)[0]
    assert "result" not in row.__dict__


# ---------- the same account live auto-trading would have run ----------


@pytest.mark.parametrize("risk", [
    {"enabled": False},
    {"enabled": True, "max_risk_per_trade_pct": 2, "stop_loss_pct": 5, "max_allocation_pct": 30, "max_open_positions": 2},
])
def test_a_portfolio_backtest_trades_like_live_auto_trading_over_the_same_days(client, market, risk):
    client.patch("/api/risk-settings", json=risk)
    for symbol in ("ALPHA", "BETA", "GAMMA"):  # created in symbol order: live tries them in that order each day
        r = client.post("/api/strategies", json={"symbol": symbol, "type": "ma_crossover", "params": {"fast": 5, "slow": 20}, "quantity": 10, "auto_trade": True})
        assert r.status_code in (200, 201), r.text
    first_day = None
    for _ in range(120):
        status = client.post("/api/market/advance", json={"days": 1}).json()
        first_day = first_day or status["date"]
    last_day = status["date"]
    live = client.get("/api/trades").json()
    live_rows = sorted((t["market_date"], t["symbol"], t["side"], t["quantity"], round(t["price"], 4)) for t in live)

    body = {**RUN, "start_date": first_day, "end_date": last_day}
    out = client.post("/api/portfolio-backtests/run", json=body).json()
    mine = []
    for t in out["trades"]:
        mine.append((str(t["entry_date"]), t["symbol"], "BUY", t["quantity"], round(t["entry_price"], 4)))
        if t["exit_date"]:
            mine.append((str(t["exit_date"]), t["symbol"], "SELL", t["quantity"], round(t["exit_price"], 4)))
    assert live_rows, "the live account should have traded"
    assert sorted(mine) == live_rows
