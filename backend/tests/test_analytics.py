from datetime import date, datetime, time

import pytest

from backend.app.models import PriceData, Stock, Trade
from backend.app.models.portfolio import INITIAL_VIRTUAL_CASH
from backend.app.services import analytics_service, market_service, strategy_service, trading_service


def set_prices(db, symbol, closes):
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    db.query(PriceData).filter(PriceData.stock_id == stock.id).delete()
    day = market_service.SIM_START_DATE
    for close in closes:
        db.add(
            PriceData(
                stock_id=stock.id,
                timestamp=datetime.combine(day, time.min),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1,
            )
        )
        day = market_service._business_day_after(day)
    stock.current_price = closes[-1]
    db.commit()


def make_trade(realized_pnl, strategy_id=None):
    return Trade(stock_id=1, side="SELL", quantity=1, price=10, realized_pnl=realized_pnl, strategy_id=strategy_id)


# ---------- trade_stats ----------


def test_trade_stats_on_a_mix_of_wins_and_losses():
    trades = [make_trade(100), make_trade(50), make_trade(-40), make_trade(-10)]
    stats = analytics_service.trade_stats(trades)
    assert stats["total_trades"] == 4
    assert (stats["winning_trades"], stats["losing_trades"]) == (2, 2)
    assert stats["win_rate_pct"] == 50.0
    assert stats["avg_win"] == pytest.approx(75.0)
    assert stats["avg_loss"] == pytest.approx(-25.0)
    assert stats["profit_factor"] == pytest.approx(150 / 50)


def test_trade_stats_ignores_open_trades_without_realized_pnl():
    trades = [make_trade(100), Trade(stock_id=1, side="BUY", quantity=1, price=10, realized_pnl=None)]
    stats = analytics_service.trade_stats(trades)
    assert stats["total_trades"] == 1


def test_trade_stats_profit_factor_is_none_with_no_losses():
    stats = analytics_service.trade_stats([make_trade(100), make_trade(50)])
    assert stats["profit_factor"] is None
    assert stats["avg_loss"] == 0.0


def test_trade_stats_on_empty_trades():
    stats = analytics_service.trade_stats([])
    assert stats == {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate_pct": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "profit_factor": None,
    }


# ---------- equity_metrics ----------


def test_equity_metrics_max_drawdown_and_sharpe():
    curve = [
        {"date": date(2025, 1, i + 1), "value": v}
        for i, v in enumerate([100_000, 110_000, 99_000, 105_000, 90_000, 120_000])
    ]
    metrics = analytics_service.equity_metrics(curve)
    # peak 110,000 -> trough 90,000 is the deepest drawdown
    assert metrics["max_drawdown_pct"] == pytest.approx((110_000 - 90_000) / 110_000 * 100)
    assert metrics["sharpe_ratio"] is not None


def test_equity_metrics_short_curve_has_no_sharpe():
    metrics = analytics_service.equity_metrics([{"date": date(2025, 1, 1), "value": 100_000}])
    assert metrics == {"max_drawdown_pct": 0.0, "sharpe_ratio": None}


def test_equity_metrics_flat_curve_has_zero_drawdown_and_no_sharpe():
    curve = [{"date": date(2025, 1, i + 1), "value": 100_000} for i in range(5)]
    metrics = analytics_service.equity_metrics(curve)
    assert metrics == {"max_drawdown_pct": 0.0, "sharpe_ratio": None}  # zero stdev -> undefined Sharpe


# ---------- drawdown_curve ----------


def test_drawdown_curve_tracks_decline_from_the_running_peak():
    curve = [{"date": date(2025, 1, i + 1), "value": v} for i, v in enumerate([100, 120, 90, 120, 60])]
    dd = analytics_service.drawdown_curve(curve)
    assert [round(p["value"], 2) for p in dd] == [0.0, 0.0, -25.0, 0.0, -50.0]


# ---------- monthly_returns ----------


def test_monthly_returns_computed_against_initial_capital_and_prior_month_end():
    curve = [
        {"date": date(2025, 1, 5), "value": INITIAL_VIRTUAL_CASH},
        {"date": date(2025, 1, 20), "value": 110_000},  # Jan ends at 110,000: +10%
        {"date": date(2025, 2, 10), "value": 99_000},  # Feb ends at 99,000: -10% from Jan's 110,000
    ]
    result = analytics_service.monthly_returns(curve, INITIAL_VIRTUAL_CASH)
    assert [(r["month"], round(r["return_pct"], 2)) for r in result] == [("2025-01", 10.0), ("2025-02", -10.0)]


def test_monthly_returns_on_empty_curve():
    assert analytics_service.monthly_returns([], INITIAL_VIRTUAL_CASH) == []


# ---------- strategy_comparison + API integration ----------


def test_strategy_comparison_groups_manual_and_strategy_trades_separately(db_session):
    strategy = strategy_service.create_strategy(db_session, "ALPHA", {"fast": 2, "slow": 3}, quantity=5)
    set_prices(db_session, "ALPHA", [100])
    set_prices(db_session, "BETA", [50])

    trading_service.execute_buy(db_session, "ALPHA", 5, strategy_id=strategy.id)
    set_prices(db_session, "ALPHA", [100, 120])
    trading_service.execute_sell(db_session, "ALPHA", 5, strategy_id=strategy.id)  # strategy profit

    trading_service.execute_buy(db_session, "BETA", 10)
    set_prices(db_session, "BETA", [50, 40])
    trading_service.execute_sell(db_session, "BETA", 10)  # manual loss

    rows = analytics_service.strategy_comparison(db_session)
    by_name = {r["name"]: r for r in rows}
    assert by_name[strategy.name]["total_pnl"] == pytest.approx(100.0)
    assert by_name["Manual"]["total_pnl"] == pytest.approx(-100.0)
    assert rows[0]["name"] == strategy.name  # sorted by total P&L, best first


def test_performance_endpoint_shape_with_no_trades(client):
    body = client.get("/api/analytics/performance").json()
    assert body["trade_stats"]["total_trades"] == 0
    assert body["by_strategy"] == []
    assert body["trade_pnls"] == []
    assert body["sharpe_ratio"] is None


def test_performance_endpoint_reflects_real_trades(client, db_session):
    set_prices(db_session, "ALPHA", [100])
    trading_service.execute_buy(db_session, "ALPHA", 10)
    set_prices(db_session, "ALPHA", [100, 130])
    trading_service.execute_sell(db_session, "ALPHA", 10)

    body = client.get("/api/analytics/performance").json()
    assert body["trade_stats"]["total_trades"] == 1
    assert body["trade_stats"]["winning_trades"] == 1
    assert body["trade_pnls"] == [pytest.approx(300.0)]
    assert body["by_strategy"][0]["name"] == "Manual"
    assert len(body["equity_curve"]) == len(body["drawdown_curve"])
