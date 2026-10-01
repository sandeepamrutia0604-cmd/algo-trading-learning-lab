from datetime import date

from backend.app.adapters.base import Candle, MarketDataAdapter
from backend.app.models import PriceData, Stock
from backend.app.services import market_service
from backend.app.services.real_stocks import import_all_real_stocks, import_real_stock


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
