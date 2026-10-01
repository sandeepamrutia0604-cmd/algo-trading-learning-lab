from datetime import datetime, time

import pytest

from backend.app.adapters import AngelOneMarketDataAdapter, DummyMarketDataAdapter, MarketDataAdapter, get_market_data_adapter
from backend.app.adapters.base import Candle
from backend.app.config import settings
from backend.app.models import PriceData, Stock
from backend.app.services import market_service
from backend.app.services.exceptions import StockNotFoundError


def set_prices(db, symbol, closes):
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    db.query(PriceData).filter(PriceData.stock_id == stock.id).delete()
    day = market_service.SIM_START_DATE
    for close in closes:
        db.add(
            PriceData(
                stock_id=stock.id,
                timestamp=datetime.combine(day, time.min),
                open=close - 1,
                high=close + 1,
                low=close - 2,
                close=close,
                volume=1000,
            )
        )
        day = market_service._business_day_after(day)
    stock.current_price = closes[-1]
    db.commit()


# ---------- the interface ----------


def test_market_data_adapter_is_abstract():
    with pytest.raises(TypeError):
        MarketDataAdapter()


# ---------- dummy adapter ----------


def test_dummy_adapter_returns_full_ohlcv_candles_oldest_first(db_session):
    set_prices(db_session, "ALPHA", [100, 105, 95])
    adapter = DummyMarketDataAdapter(db_session)

    candles = adapter.get_historical_candles("ALPHA")
    assert [c.close for c in candles] == [100, 105, 95]
    assert candles[0] == Candle(date=market_service.SIM_START_DATE, open=99, high=101, low=98, close=100, volume=1000)


def test_dummy_adapter_respects_limit(db_session):
    set_prices(db_session, "ALPHA", [100, 105, 95, 110])
    adapter = DummyMarketDataAdapter(db_session)

    candles = adapter.get_historical_candles("ALPHA", limit=2)
    assert [c.close for c in candles] == [95, 110]  # most recent 2, still oldest-first


def test_dummy_adapter_raises_for_unknown_symbol(db_session):
    with pytest.raises(StockNotFoundError):
        DummyMarketDataAdapter(db_session).get_historical_candles("NOPE")


def test_dummy_adapter_latest_price(db_session):
    adapter = DummyMarketDataAdapter(db_session)
    assert adapter.get_latest_price("ALPHA") is None  # no history seeded in this fixture

    set_prices(db_session, "ALPHA", [100, 105, 95])
    assert adapter.get_latest_price("ALPHA") == 95


# ---------- Angel One adapter (designed, not wired up) ----------


def test_angel_one_adapter_constructs_without_credentials():
    AngelOneMarketDataAdapter(api_key="", client_code="")  # should not raise


def test_angel_one_adapter_data_methods_raise_not_implemented():
    adapter = AngelOneMarketDataAdapter(api_key="key", client_code="client")
    with pytest.raises(NotImplementedError, match="Phase 12"):
        adapter.get_historical_candles("RELIANCE")
    with pytest.raises(NotImplementedError, match="Phase 12"):
        adapter.get_latest_price("RELIANCE")


def test_angel_one_adapter_resolves_a_configured_instrument_token():
    adapter = AngelOneMarketDataAdapter(api_key="key", client_code="client", instrument_token_map={"RELIANCE": "2885"})
    assert adapter.resolve_instrument_token("reliance") == "2885"  # case-insensitive


def test_angel_one_adapter_unresolved_token_raises_not_implemented():
    adapter = AngelOneMarketDataAdapter(api_key="key", client_code="client")
    with pytest.raises(NotImplementedError):
        adapter.resolve_instrument_token("RELIANCE")


# ---------- factory ----------


def test_factory_defaults_to_the_dummy_adapter(db_session):
    assert isinstance(get_market_data_adapter(db_session), DummyMarketDataAdapter)


def test_factory_selects_angel_one_when_configured(db_session):
    original = settings.market_data_provider
    settings.market_data_provider = "angel_one"
    try:
        assert isinstance(get_market_data_adapter(db_session), AngelOneMarketDataAdapter)
    finally:
        settings.market_data_provider = original
