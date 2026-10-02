from datetime import date

import pytest

from backend.app.adapters.base import Candle, MarketDataAdapter
from backend.app.models import PriceData, Stock
from backend.app.services import market_service, trading_service
from backend.app.services.real_stocks import import_all_real_stocks, import_candles, import_real_stock


class FakeAdapter(MarketDataAdapter):
    def __init__(self, candles_by_symbol: dict[str, list[Candle]]):
        self.candles_by_symbol = candles_by_symbol

    def get_historical_candles(self, symbol, limit=None):
        candles = self.candles_by_symbol[symbol]
        return candles[-limit:] if limit else candles

    def get_latest_price(self, symbol):
        candles = self.get_historical_candles(symbol)
        return candles[-1].close if candles else None


def make_candles(closes: list[float]) -> list[Candle]:
    return [
        Candle(date=date(2025, 1, i + 1), open=c, high=c + 1, low=c - 1, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


def test_import_real_stock_creates_a_stock_with_real_history(db_session):
    adapter = FakeAdapter({"RELIANCE": make_candles([100.0, 110.0, 105.0])})

    stock = import_real_stock(db_session, adapter, "RELIANCE", "Reliance Industries")
    db_session.commit()

    assert stock.source == "angel_one"
    assert stock.starting_price == 100.0
    assert stock.current_price == 105.0
    rows = db_session.query(PriceData).filter(PriceData.stock_id == stock.id).order_by(PriceData.timestamp).all()
    assert [r.close for r in rows] == [100.0, 110.0, 105.0]


def test_reimport_replaces_the_existing_history(db_session):
    adapter = FakeAdapter({"RELIANCE": make_candles([100.0, 110.0])})
    import_real_stock(db_session, adapter, "RELIANCE", "Reliance Industries")
    db_session.commit()

    adapter.candles_by_symbol["RELIANCE"] = make_candles([200.0, 210.0, 220.0])
    stock = import_real_stock(db_session, adapter, "RELIANCE", "Reliance Industries")
    db_session.commit()

    rows = db_session.query(PriceData).filter(PriceData.stock_id == stock.id).all()
    assert len(rows) == 3
    assert stock.current_price == 220.0


def test_simulator_never_touches_an_imported_real_stock(db_session):
    adapter = FakeAdapter({"RELIANCE": make_candles([100.0, 110.0, 105.0])})
    import_all_real_stocks(db_session, adapter, [{"symbol": "RELIANCE", "name": "Reliance Industries"}])

    market_service.generate_all(db_session, 20, seed=1)
    market_service.advance(db_session, 5)
    market_service.reset_market(db_session)

    stock = db_session.query(Stock).filter(Stock.symbol == "RELIANCE").first()
    rows = db_session.query(PriceData).filter(PriceData.stock_id == stock.id).order_by(PriceData.timestamp).all()
    assert [r.close for r in rows] == [100.0, 110.0, 105.0]

    # the simulated stocks are unaffected by the real stock's presence -- reset_market put
    # them back to the default seeded history length, same as it would with no real stock
    for symbol in ("ALPHA", "BETA", "GAMMA", "DELTA"):
        assert len(market_service.get_prices(db_session, symbol)) == market_service.DEFAULT_HISTORY_DAYS


# ---------- importing candles from a file (source="csv") ----------


def candles_on(days: list[int], close: float) -> list[Candle]:
    return [Candle(date=date(2025, 1, d), open=close, high=close + 1, low=close - 1, close=close, volume=10) for d in days]


def stored_closes(db, stock):
    rows = db.query(PriceData).filter(PriceData.stock_id == stock.id).order_by(PriceData.timestamp).all()
    return [(r.timestamp.date().day, r.close) for r in rows]


def test_importing_a_new_symbol_creates_a_csv_stock(db_session):
    stock = import_candles(db_session, "reliance", "Reliance Industries", candles_on([1, 2, 3], 100.0), source="csv", replace=False)
    db_session.commit()

    assert (stock.symbol, stock.name, stock.source) == ("RELIANCE", "Reliance Industries", "csv")
    assert (stock.starting_price, stock.current_price) == (100.0, 100.0)
    assert len(stored_closes(db_session, stock)) == 3


def test_merge_adds_new_days_and_overwrites_overlapping_ones_without_losing_the_rest(db_session):
    import_candles(db_session, "TCS", "TCS", candles_on([1, 2, 3], 100.0), source="csv", replace=False)
    stock = import_candles(db_session, "TCS", None, candles_on([3, 4], 150.0), source="csv", replace=False)
    db_session.commit()

    assert stored_closes(db_session, stock) == [(1, 100.0), (2, 100.0), (3, 150.0), (4, 150.0)]
    assert stock.starting_price == 100.0
    assert stock.current_price == 150.0


def test_a_merge_of_older_days_moves_starting_price_but_not_current_price(db_session):
    import_candles(db_session, "TCS", "TCS", candles_on([5, 6], 200.0), source="csv", replace=False)
    stock = import_candles(db_session, "TCS", None, candles_on([1, 2], 120.0), source="csv", replace=False)

    assert stock.starting_price == 120.0
    assert stock.current_price == 200.0


def test_replace_discards_existing_history(db_session):
    import_candles(db_session, "TCS", "TCS", candles_on([1, 2, 3], 100.0), source="csv", replace=False)
    stock = import_candles(db_session, "TCS", None, candles_on([10], 300.0), source="csv", replace=True)

    assert stored_closes(db_session, stock) == [(10, 300.0)]


def test_merging_into_an_angel_one_stock_keeps_its_source_and_name(db_session):
    import_candles(db_session, "INFY", "Infosys", candles_on([1, 2], 100.0), source="angel_one", replace=True)
    stock = import_candles(db_session, "INFY", None, candles_on([3], 110.0), source="csv", replace=False)

    assert (stock.source, stock.name) == ("angel_one", "Infosys")


def test_a_simulated_stock_cannot_be_imported_over(db_session):
    with pytest.raises(ValueError, match="simulated"):
        import_candles(db_session, "ALPHA", None, candles_on([1], 100.0), source="csv", replace=True)


def test_importing_nothing_is_an_error(db_session):
    with pytest.raises(ValueError, match="No candles"):
        import_candles(db_session, "TCS", None, [], source="csv", replace=False)


def test_the_simulator_leaves_a_csv_stock_alone(db_session):
    stock = import_candles(db_session, "TCS", "TCS", candles_on([1, 2, 3], 100.0), source="csv", replace=False)
    db_session.commit()

    market_service.generate_all(db_session, 20, seed=1)
    market_service.advance(db_session, 5)

    assert stored_closes(db_session, stock) == [(1, 100.0), (2, 100.0), (3, 100.0)]


def test_reset_puts_a_real_stock_at_its_latest_close_not_its_oldest(db_session):
    stock = import_candles(
        db_session, "TCS", "TCS", candles_on([1], 100.0) + candles_on([2], 250.0), source="csv", replace=False
    )
    stock.current_price = 999.0
    db_session.commit()

    trading_service.reset_simulation(db_session)

    assert stock.starting_price == 100.0
    assert stock.current_price == 250.0
