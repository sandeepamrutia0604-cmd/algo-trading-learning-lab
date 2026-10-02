import pytest

from backend.app.engine.backtest import RiskConfig, run_backtest
from backend.app.engine.cost_math import CostConfig, charges, fill_price
from backend.app.models import Position
from backend.app.models.portfolio import INITIAL_VIRTUAL_CASH
from backend.app.services import cost_service, market_service, portfolio_service, trading_service
from backend.app.services.exceptions import InsufficientFundsError
from backend.app.strategies.base import SignalEvent
from backend.tests.test_backtest import make_dates, make_defn

COSTS = CostConfig(enabled=True, slippage_pct=0.5, brokerage_pct=0.03, brokerage_cap=20.0, other_charges_pct=0.1)


def enable_costs(db, **overrides):
    fields = {"enabled": True, "slippage_pct": 0.5, "brokerage_pct": 0.03, "brokerage_cap": 20.0, "other_charges_pct": 0.1}
    return cost_service.update_settings(db, **{**fields, **overrides})


def buy_signal(index):
    return SignalEvent(index=index, side="BUY", headline="", checks=[], values={})


def sell_signal(index):
    return SignalEvent(index=index, side="SELL", headline="", checks=[], values={})


# ---------- the pure formulas ----------


def test_nothing_changes_while_costs_are_disabled():
    off = CostConfig(enabled=False, slippage_pct=1, brokerage_pct=1, brokerage_cap=5, other_charges_pct=1)

    assert fill_price(100, "BUY", off) == 100
    assert fill_price(100, "SELL", off) == 100
    assert charges(1_00_000, off) == 0.0


def test_slippage_moves_the_fill_against_you_on_both_sides():
    assert fill_price(100, "BUY", COSTS) == 100.5
    assert fill_price(100, "SELL", COSTS) == 99.5


def test_brokerage_is_a_percentage_of_the_trade_value_plus_taxes():
    # 0.03% of 10,000 = 3.00 brokerage (under the 20 cap), plus 0.1% = 10.00 taxes
    assert charges(10_000, COSTS) == pytest.approx(13.0)


def test_brokerage_is_capped_per_order_but_taxes_are_not():
    # 0.03% of 1,00,000 = 30 -> capped at 20; taxes 0.1% = 100
    assert charges(1_00_000, COSTS) == pytest.approx(120.0)


def test_a_zero_cap_means_no_cap():
    uncapped = CostConfig(enabled=True, brokerage_pct=0.03, brokerage_cap=0.0, other_charges_pct=0.1)
    assert charges(1_00_000, uncapped) == pytest.approx(130.0)


def test_an_empty_order_costs_nothing():
    assert charges(0, COSTS) == 0.0


# ---------- paper trading ----------


def test_a_buy_fills_above_the_quote_and_charges_come_out_of_cash(db_session):
    enable_costs(db_session)
    trade = trading_service.execute_buy(db_session, "ALPHA", 100)  # quoted at 100.00

    assert trade.market_price == 100.0
    assert trade.price == 100.5
    assert trade.fees == pytest.approx(13.07, abs=0.01)  # 3.02 brokerage + 10.05 taxes on 10,050
    cash = trading_service.get_portfolio(db_session).virtual_cash
    assert cash == pytest.approx(INITIAL_VIRTUAL_CASH - 10_050 - trade.fees)


def test_the_position_cost_basis_includes_the_buy_side_charges(db_session):
    enable_costs(db_session)
    trade = trading_service.execute_buy(db_session, "ALPHA", 100)

    position = db_session.query(Position).first()
    assert position.average_price == pytest.approx((10_050 + trade.fees) / 100)


def test_a_round_trip_at_an_unchanged_price_loses_exactly_what_it_cost(db_session):
    enable_costs(db_session)
    buy = trading_service.execute_buy(db_session, "ALPHA", 100)
    sell = trading_service.execute_sell(db_session, "ALPHA", 100)

    portfolio = trading_service.get_portfolio(db_session)
    assert sell.price == 99.5
    assert portfolio.virtual_cash < INITIAL_VIRTUAL_CASH
    # flat price, fully closed: realized P&L is precisely the cash that was lost
    assert portfolio.realized_pnl == pytest.approx(portfolio.virtual_cash - INITIAL_VIRTUAL_CASH)
    assert sell.realized_pnl == pytest.approx(portfolio.realized_pnl)
    slippage_loss = (100.5 - 99.5) * 100
    assert -portfolio.realized_pnl == pytest.approx(slippage_loss + buy.fees + sell.fees)


def test_affordability_includes_the_charges(db_session):
    # 995 shares at 100.5 is 99,997.50 -- inside 1,00,000 of cash, but not once charges are added
    enable_costs(db_session)
    with pytest.raises(InsufficientFundsError, match="charges"):
        trading_service.execute_buy(db_session, "ALPHA", 995)


def test_with_costs_off_a_buy_fills_at_the_quote_with_no_charges(db_session):
    trade = trading_service.execute_buy(db_session, "ALPHA", 100)

    assert (trade.price, trade.market_price, trade.fees) == (100.0, 100.0, 0.0)
    assert trading_service.get_portfolio(db_session).virtual_cash == INITIAL_VIRTUAL_CASH - 10_000


def test_the_equity_curve_ends_where_the_portfolio_value_does(db_session):
    market_service.generate_all(db_session, 10, seed=1)
    enable_costs(db_session)
    trading_service.execute_buy(db_session, "ALPHA", 200)
    trading_service.execute_buy(db_session, "BETA", 50)
    trading_service.execute_sell(db_session, "ALPHA", 80)

    curve = portfolio_service.get_equity_curve(db_session)
    summary = portfolio_service.get_portfolio_summary(db_session)

    assert curve[-1]["value"] == pytest.approx(summary["portfolio_value"], abs=0.01)


# ---------- backtests ----------


def run(closes, events, costs=None, risk=None, quantity=10, capital=1_00_000):
    return run_backtest(make_defn(events), {}, make_dates(len(closes)), closes, quantity, capital, risk, costs)


def test_a_backtest_with_costs_off_is_unchanged():
    closes = [100, 100, 110]
    plain = run(closes, [buy_signal(0), sell_signal(2)])
    off = run(closes, [buy_signal(0), sell_signal(2)], costs=CostConfig(enabled=False, slippage_pct=1, brokerage_pct=1))

    assert plain.final_capital == off.final_capital == 1_00_000 + 100
    assert (off.total_fees, off.slippage_cost, off.costs_applied) == (0.0, 0.0, False)


def test_a_backtest_round_trip_pays_slippage_and_charges_on_both_sides():
    closes = [100, 100, 110]
    result = run(closes, [buy_signal(0), sell_signal(2)], costs=COSTS, quantity=100)

    trade = result.trades[0]
    assert (trade.entry_price, trade.exit_price) == (100.5, 109.45)  # 110 less 0.5% slippage
    buy_fees, sell_fees = trade.entry_fees, trade.exit_fees
    assert buy_fees == pytest.approx(charges(10_050, COSTS))
    assert sell_fees == pytest.approx(charges(10_945, COSTS))
    gross = (109.45 - 100.5) * 100
    assert trade.pnl == pytest.approx(gross - buy_fees - sell_fees)
    assert result.final_capital == pytest.approx(1_00_000 + trade.pnl)
    assert result.total_fees == pytest.approx(buy_fees + sell_fees)
    assert result.slippage_cost == pytest.approx(0.5 * 100 + 0.55 * 100)  # 50 going in, 55 going out
    assert result.costs_applied is True


def test_costs_turn_a_marginal_winner_into_a_loser():
    closes = [100, 100, 100.4]  # +0.4% before costs
    free = run(closes, [buy_signal(0), sell_signal(2)], quantity=100)
    costly = run(closes, [buy_signal(0), sell_signal(2)], costs=COSTS, quantity=100)

    assert free.trades[0].pnl > 0
    assert costly.trades[0].pnl < 0


def test_the_equity_curve_dips_by_the_entry_costs_immediately():
    result = run([100, 100], [buy_signal(0)], costs=COSTS, quantity=100)

    # bought at 100.5 plus charges but marked at the 100 close: down by slippage + charges at once
    assert result.equity_curve[0].value == pytest.approx(1_00_000 - 50 - result.total_fees)


def test_a_buy_is_skipped_when_the_charges_leave_too_little_cash():
    # 99 shares at 100.5 = 9,949.50; the charges push it past 9,950 of capital
    result = run([100, 100], [buy_signal(0)], costs=COSTS, quantity=99, capital=9_950)

    assert result.trades == []
    assert result.skipped_buys == 1


def test_a_stop_loss_exit_pays_the_sell_side_costs_too():
    risk = RiskConfig(enabled=True, stop_loss_pct=5)
    result = run([100, 100, 94], [buy_signal(0)], costs=COSTS, risk=risk, quantity=100)

    trade = result.trades[0]
    assert trade.stopped_out and trade.exit_price == 93.53  # 94 less 0.5%
    assert trade.exit_fees > 0
    assert trade.pnl == pytest.approx((93.53 - 100.5) * 100 - trade.entry_fees - trade.exit_fees)


def test_the_service_backtest_uses_the_saved_cost_settings(db_session):
    from backend.app.services import backtest_service

    market_service.generate_all(db_session, 60, seed=1)
    free = backtest_service.run(db_session, "ALPHA", "ma_crossover", {"fast": 5, "slow": 20}, 10, 1_00_000)[4]
    enable_costs(db_session)
    costly = backtest_service.run(db_session, "ALPHA", "ma_crossover", {"fast": 5, "slow": 20}, 10, 1_00_000)[4]

    assert free.total_trades > 0 and not free.costs_applied
    assert costly.costs_applied and costly.total_fees > 0
    assert costly.final_capital < free.final_capital


# ---------- the API ----------


def test_cost_settings_default_to_off_and_round_trip(client):
    defaults = client.get("/api/cost-settings").json()
    assert defaults["enabled"] is False

    updated = client.patch("/api/cost-settings", json={"enabled": True, "slippage_pct": 0.2}).json()
    assert updated["enabled"] is True and updated["slippage_pct"] == 0.2
    assert client.get("/api/cost-settings").json() == updated


def test_cost_settings_reject_out_of_range_values(client):
    assert client.patch("/api/cost-settings", json={"slippage_pct": -1}).status_code == 422
    assert client.patch("/api/cost-settings", json={"brokerage_pct": 50}).status_code == 422
    assert client.patch("/api/cost-settings", json={"brokerage_cap": -5}).status_code == 422


def test_orders_and_trades_report_fees_and_the_quoted_price(client):
    client.patch("/api/cost-settings", json={"enabled": True, "slippage_pct": 0.5})
    client.post("/api/orders/buy", json={"symbol": "ALPHA", "quantity": 10})

    trade = client.get("/api/trades").json()[0]
    assert trade["market_price"] == 100.0
    assert trade["price"] == 100.5
    assert trade["fees"] > 0


def test_the_backtest_endpoint_reports_what_the_costs_came_to(client, db_session):
    market_service.generate_all(db_session, 60, seed=1)
    client.patch("/api/cost-settings", json={"enabled": True})
    body = {"symbol": "ALPHA", "type": "ma_crossover", "params": {"fast": 5, "slow": 20}, "quantity": 10, "initial_capital": 100000}

    result = client.post("/api/backtests/run", json=body).json()

    assert result["costs_applied"] is True
    assert result["total_fees"] > 0
    assert result["slippage_cost"] > 0
