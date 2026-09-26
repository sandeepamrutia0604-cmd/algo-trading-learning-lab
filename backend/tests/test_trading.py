import pytest

from backend.app.models import Position
from backend.app.models.portfolio import INITIAL_VIRTUAL_CASH
from backend.app.services import trading_service
from backend.app.services.exceptions import (
    InsufficientFundsError,
    InsufficientSharesError,
    InvalidQuantityError,
    StockNotFoundError,
)
from backend.app.services.portfolio_service import get_portfolio_summary


def test_buy_deducts_cash_and_opens_position(db_session):
    trading_service.execute_buy(db_session, "ALPHA", 100)

    portfolio = trading_service.get_portfolio(db_session)
    assert portfolio.virtual_cash == INITIAL_VIRTUAL_CASH - 100 * 100.0

    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    position = db_session.query(Position).filter(Position.stock_id == stock.id).first()
    assert position.quantity == 100
    assert position.average_price == 100.0


def test_buy_averages_price_across_multiple_purchases(db_session):
    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")

    trading_service.execute_buy(db_session, "ALPHA", 100)  # @100
    stock.current_price = 120.0
    db_session.commit()
    trading_service.execute_buy(db_session, "ALPHA", 100)  # @120

    position = db_session.query(Position).filter(Position.stock_id == stock.id).first()
    assert position.quantity == 200
    assert position.average_price == pytest.approx(110.0)


def test_buy_rejects_when_cost_exceeds_cash(db_session):
    with pytest.raises(InsufficientFundsError):
        trading_service.execute_buy(db_session, "DELTA", 1_000_000)


def test_buy_rejects_non_positive_quantity(db_session):
    with pytest.raises(InvalidQuantityError):
        trading_service.execute_buy(db_session, "ALPHA", 0)


def test_buy_rejects_unknown_symbol(db_session):
    with pytest.raises(StockNotFoundError):
        trading_service.execute_buy(db_session, "ZZZZ", 10)


def test_sell_without_position_is_rejected(db_session):
    with pytest.raises(InsufficientSharesError):
        trading_service.execute_sell(db_session, "ALPHA", 10)


def test_sell_more_than_held_is_rejected(db_session):
    trading_service.execute_buy(db_session, "ALPHA", 10)
    with pytest.raises(InsufficientSharesError):
        trading_service.execute_sell(db_session, "ALPHA", 11)


def test_sell_realizes_pnl_and_closes_position_at_zero(db_session):
    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    trading_service.execute_buy(db_session, "ALPHA", 100)  # cost basis @100

    stock.current_price = 108.0
    db_session.commit()
    trading_service.execute_sell(db_session, "ALPHA", 100)

    portfolio = trading_service.get_portfolio(db_session)
    assert portfolio.realized_pnl == pytest.approx(800.0)  # (108-100)*100
    assert portfolio.virtual_cash == pytest.approx(INITIAL_VIRTUAL_CASH + 800.0)

    position = db_session.query(Position).filter(Position.stock_id == stock.id).first()
    assert position is None


def test_partial_sell_keeps_average_price(db_session):
    trading_service.execute_buy(db_session, "ALPHA", 100)
    trading_service.execute_sell(db_session, "ALPHA", 40)

    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    position = db_session.query(Position).filter(Position.stock_id == stock.id).first()
    assert position.quantity == 60
    assert position.average_price == 100.0


def test_portfolio_summary_matches_manual_calculation(db_session):
    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    trading_service.execute_buy(db_session, "ALPHA", 100)  # spend 10,000 @100
    stock.current_price = 108.0
    db_session.commit()

    summary = get_portfolio_summary(db_session)

    assert summary["cash"] == pytest.approx(INITIAL_VIRTUAL_CASH - 10_000)
    assert summary["invested"] == pytest.approx(10_000)
    assert summary["market_value"] == pytest.approx(10_800)
    assert summary["unrealized_pnl"] == pytest.approx(800)
    assert summary["portfolio_value"] == pytest.approx(INITIAL_VIRTUAL_CASH + 800)
    assert summary["total_pnl"] == pytest.approx(800)


def test_reset_simulation_restores_initial_state(db_session):
    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    trading_service.execute_buy(db_session, "ALPHA", 100)
    stock.current_price = 120.0
    db_session.commit()
    trading_service.execute_sell(db_session, "ALPHA", 50)

    trading_service.reset_simulation(db_session)

    portfolio = trading_service.get_portfolio(db_session)
    assert portfolio.virtual_cash == INITIAL_VIRTUAL_CASH
    assert portfolio.realized_pnl == 0.0
    assert db_session.query(Position).count() == 0

    refreshed_stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    assert refreshed_stock.current_price == refreshed_stock.starting_price


def test_trades_record_market_date_and_realized_pnl(db_session):
    from backend.app.services import market_service

    market_service.generate_all(db_session, 10, seed=1)
    market_date = market_service.latest_market_date(db_session)
    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")

    buy = trading_service.execute_buy(db_session, "ALPHA", 10)
    stock.current_price = stock.current_price + 5
    db_session.commit()
    sell = trading_service.execute_sell(db_session, "ALPHA", 4)

    assert buy.market_date == market_date
    assert buy.realized_pnl is None
    assert sell.market_date == market_date
    assert sell.realized_pnl == pytest.approx(20.0)  # (+5 per share) * 4


def test_trade_market_date_is_none_without_price_history(db_session):
    trade = trading_service.execute_buy(db_session, "ALPHA", 1)
    assert trade.market_date is None
