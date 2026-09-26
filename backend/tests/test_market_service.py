from datetime import timedelta

import pytest

from backend.app.models import PriceData
from backend.app.services import market_service, trading_service
from backend.app.services.exceptions import StockNotFoundError
from backend.app.services.seed import ensure_seed_data


def closes(db, symbol):
    return [r.close for r in market_service.get_prices(db, symbol)]


def test_generate_all_creates_history_and_updates_current_price(db_session):
    market_service.generate_all(db_session, 20, seed=1)

    for symbol in ("ALPHA", "BETA", "GAMMA", "DELTA"):
        rows = market_service.get_prices(db_session, symbol)
        stock = trading_service.get_stock_by_symbol(db_session, symbol)
        assert len(rows) == 20
        assert rows[0].open == stock.starting_price
        assert stock.current_price == rows[-1].close


def test_history_dates_increase_and_skip_weekends(db_session):
    market_service.generate_all(db_session, 30, seed=1)
    dates = [r.timestamp.date() for r in market_service.get_prices(db_session, "ALPHA")]

    assert dates[0] == market_service.SIM_START_DATE
    assert all(d.weekday() < 5 for d in dates)
    assert all(b > a for a, b in zip(dates, dates[1:]))


def test_seeded_generation_is_deterministic(db_session):
    market_service.generate_all(db_session, 15, seed=7)
    first = closes(db_session, "BETA")
    market_service.generate_all(db_session, 15, seed=7)
    assert closes(db_session, "BETA") == first


def test_advance_appends_days_continuing_from_last_close(db_session):
    market_service.generate_all(db_session, 10, seed=1)
    before = market_service.get_prices(db_session, "ALPHA")

    market_service.advance(db_session, 5)
    after = market_service.get_prices(db_session, "ALPHA")

    assert len(after) == 15
    assert [r.close for r in after[:10]] == [r.close for r in before]
    next_day = before[-1].timestamp.date() + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    assert after[10].timestamp.date() == next_day

    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    assert stock.current_price == after[-1].close


def test_update_config_persists_and_rejects_unknown_symbol(db_session):
    market_service.update_config(db_session, "alpha", "trending", 0.01, 0.002)
    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    config = market_service.get_config(db_session, stock)
    assert (config.model, config.volatility, config.trend) == ("trending", 0.01, 0.002)

    with pytest.raises(StockNotFoundError):
        market_service.update_config(db_session, "ZZZZ", "trending", 0.01, 0.0)


def test_get_prices_limit_returns_latest_rows_in_order(db_session):
    market_service.generate_all(db_session, 20, seed=1)
    all_rows = market_service.get_prices(db_session, "ALPHA")
    last_five = market_service.get_prices(db_session, "ALPHA", limit=5)
    assert [r.close for r in last_five] == [r.close for r in all_rows[-5:]]


def test_reset_market_restores_default_seeded_history_and_configs(db_session):
    ensure_seed_data(db_session)  # builds the default seeded history
    default_closes = closes(db_session, "ALPHA")

    market_service.update_config(db_session, "ALPHA", "volatile", 0.05, 0.01)
    market_service.advance(db_session, 10)
    market_service.reset_market(db_session)

    assert closes(db_session, "ALPHA") == default_closes
    assert db_session.query(PriceData).filter(PriceData.stock_id == 1).count() == 60
    stock = trading_service.get_stock_by_symbol(db_session, "ALPHA")
    config = market_service.get_config(db_session, stock)
    assert (config.model, config.volatility, config.trend) == ("random_walk", 0.02, 0.0)


def test_seed_with_history_gives_every_stock_a_default_history(db_session):
    ensure_seed_data(db_session)
    for symbol in ("ALPHA", "BETA", "GAMMA", "DELTA"):
        assert len(market_service.get_prices(db_session, symbol)) == market_service.DEFAULT_HISTORY_DAYS
