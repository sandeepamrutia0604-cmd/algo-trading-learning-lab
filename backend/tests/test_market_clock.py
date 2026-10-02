from datetime import date, timedelta

from backend.app.adapters import get_market_data_adapter
from backend.app.adapters.base import Candle
from backend.app.models import Portfolio, PriceData, Stock
from backend.app.services import market_service, portfolio_service
from backend.app.services.real_stocks import import_candles
from backend.app.services.seed import ensure_seed_data


def weekday_candles(start: date, count: int, base: float = 1000.0) -> list[Candle]:
    """`count` consecutive weekday candles whose close is base + index, so a close identifies
    exactly how many candles have been revealed."""
    candles, day, i = [], start, 0
    while len(candles) < count:
        if day.weekday() < 5:
            candles.append(Candle(date=day, open=base + i, high=base + i + 1, low=base + i - 1, close=base + i, volume=100))
            i += 1
        day += timedelta(days=1)
    return candles


def import_real(db, symbol="REAL", start=date(2025, 9, 1), count=200):
    candles = weekday_candles(start, count)
    stock = import_candles(db, symbol, symbol, candles, source="csv", replace=False)
    db.commit()
    return stock, candles


def visible_closes(db, symbol):
    return [r.close for r in market_service.get_prices(db, symbol)]


def clock(db):
    return market_service.current_date(db)


def start_market(db):
    ensure_seed_data(db)  # default 60-day simulated history, clock at its end


def test_a_new_real_stock_starts_with_warmup_history_and_the_clock_moves_up_to_it(db_session):
    start_market(db_session)
    sim_clock = clock(db_session)
    stock, candles = import_real(db_session)

    assert clock(db_session) == candles[market_service.WARMUP_DAYS - 1].date > sim_clock
    assert len(visible_closes(db_session, "REAL")) == market_service.WARMUP_DAYS
    assert stock.current_price == candles[market_service.WARMUP_DAYS - 1].close


def test_simulated_stocks_are_extended_to_the_new_clock_so_everything_shares_one_calendar(db_session):
    start_market(db_session)
    import_real(db_session)

    for symbol in ("ALPHA", "BETA", "GAMMA", "DELTA"):
        rows = market_service.get_prices(db_session, symbol)
        assert rows[-1].timestamp.date() == clock(db_session)
        assert len(rows) == market_service._count_business_days(market_service.SIM_START_DATE, clock(db_session))


def test_advancing_reveals_one_real_candle_per_day_and_updates_the_price(db_session):
    start_market(db_session)
    stock, candles = import_real(db_session)
    warm = market_service.WARMUP_DAYS

    market_service.advance(db_session, 1)
    assert clock(db_session) == candles[warm].date
    assert len(visible_closes(db_session, "REAL")) == warm + 1
    assert stock.current_price == candles[warm].close

    market_service.advance(db_session, 5)
    assert clock(db_session) == candles[warm + 5].date
    assert stock.current_price == candles[warm + 5].close


def test_simulated_stocks_keep_pace_with_the_clock_as_it_advances(db_session):
    start_market(db_session)
    import_real(db_session)

    market_service.advance(db_session, 3)

    for symbol in ("ALPHA", "DELTA"):
        assert market_service.get_prices(db_session, symbol)[-1].timestamp.date() == clock(db_session)


def test_candles_after_the_clock_are_hidden_everywhere_a_chart_or_signal_reads_prices(db_session):
    start_market(db_session)
    stock, candles = import_real(db_session)
    warm = market_service.WARMUP_DAYS

    assert len(market_service.recent_closes(db_session, stock.id, 500)) == warm
    adapter = get_market_data_adapter(db_session)
    assert len(adapter.get_historical_candles("REAL")) == warm
    assert adapter.get_latest_price("REAL") == candles[warm - 1].close


def test_backtests_get_the_full_history_not_just_what_has_happened_so_far(db_session):
    start_market(db_session)
    import_real(db_session, count=200)

    full = get_market_data_adapter(db_session, full_history=True).get_historical_candles("REAL")
    assert len(full) == 200
    assert len(market_service.get_prices(db_session, "REAL", full=True)) == 200
    assert len(market_service.get_prices(db_session, "REAL")) == market_service.WARMUP_DAYS


def test_the_clock_stops_at_the_last_real_candle(db_session):
    start_market(db_session)
    stock, candles = import_real(db_session, count=70)

    market_service.advance(db_session, 500)

    assert clock(db_session) == candles[-1].date
    assert market_service.at_end_of_real_data(db_session)
    assert stock.current_price == candles[-1].close

    market_service.advance(db_session, 5)  # nothing left to reveal
    assert clock(db_session) == candles[-1].date


def test_real_data_that_ended_before_the_clock_does_not_stop_the_market(db_session):
    start_market(db_session)
    import_real(db_session, symbol="OLD", start=date(2025, 1, 6), count=20)
    before = clock(db_session)

    market_service.advance(db_session, 3)

    assert clock(db_session) > before
    assert not market_service.at_end_of_real_data(db_session)


def test_importing_history_that_is_already_in_the_past_does_not_move_the_clock(db_session):
    start_market(db_session)
    before = clock(db_session)
    stock, candles = import_real(db_session, start=date(2025, 1, 6), count=20)

    assert clock(db_session) == before
    assert len(visible_closes(db_session, "REAL")) == 20
    assert stock.current_price == candles[-1].close


def test_a_short_series_does_not_start_with_all_of_itself_already_played_out(db_session):
    start_market(db_session)
    _, candles = import_real(db_session, count=10)

    assert 0 < len(visible_closes(db_session, "REAL")) < 10
    assert clock(db_session) < candles[-1].date


def test_reset_market_replays_real_stocks_from_their_warmup_again(db_session):
    start_market(db_session)
    import_real(db_session)
    market_service.advance(db_session, 40)

    market_service.reset_market(db_session)

    assert len(visible_closes(db_session, "REAL")) == market_service.WARMUP_DAYS
    assert market_service.get_prices(db_session, "ALPHA")[-1].timestamp.date() == clock(db_session)


def test_regenerating_simulated_history_runs_the_clock_on_to_where_real_stocks_start(db_session):
    start_market(db_session)
    _, candles = import_real(db_session)
    warm_date = candles[market_service.WARMUP_DAYS - 1].date

    market_service.generate_all(db_session, 20, seed=1)

    assert clock(db_session) == warm_date
    assert len(visible_closes(db_session, "REAL")) == market_service.WARMUP_DAYS
    assert market_service.get_prices(db_session, "ALPHA")[-1].timestamp.date() == warm_date


def test_ensure_clock_starts_a_missing_clock_without_losing_history(db_session):
    start_market(db_session)
    stock, candles = import_real(db_session)
    sim_rows_before = len(market_service.get_prices(db_session, "ALPHA"))
    db_session.query(Portfolio).first().market_date = None  # an older database, from before the clock
    db_session.commit()

    market_service.ensure_clock(db_session)

    assert db_session.query(Portfolio).first().market_date is not None
    assert len(visible_closes(db_session, "REAL")) == market_service.WARMUP_DAYS
    assert len(market_service.get_prices(db_session, "ALPHA")) >= sim_rows_before
    assert db_session.query(PriceData).filter(PriceData.stock_id == stock.id).count() == len(candles)


def test_ensure_clock_never_moves_the_clock_backwards(db_session):
    start_market(db_session)
    import_real(db_session)
    market_service.advance(db_session, 25)
    advanced = clock(db_session)

    market_service.ensure_clock(db_session)

    assert clock(db_session) == advanced


def test_the_equity_curve_only_covers_days_up_to_the_clock(db_session):
    start_market(db_session)
    import_real(db_session)

    curve = portfolio_service.get_equity_curve(db_session)

    assert curve[-1]["date"] == clock(db_session)


def test_advance_with_no_history_at_all_still_starts_from_the_beginning(db_session):
    # a database with stocks but no candles yet: advancing generates from the simulation start
    market_service.advance(db_session, 5)

    rows = market_service.get_prices(db_session, "ALPHA")
    assert len(rows) == 5
    assert rows[0].timestamp.date() == market_service.SIM_START_DATE
    assert clock(db_session) == rows[-1].timestamp.date()


def test_the_replay_never_touches_the_stored_candles(db_session):
    start_market(db_session)
    stock, candles = import_real(db_session, count=100)

    market_service.advance(db_session, 30)
    market_service.reset_market(db_session)

    stored = db_session.query(PriceData).filter(PriceData.stock_id == stock.id).order_by(PriceData.timestamp).all()
    assert [r.close for r in stored] == [c.close for c in candles]


# ---------- through the API ----------


def test_api_advance_reports_when_the_real_data_runs_out(client, db_session):
    start_market(db_session)
    import_real(db_session, count=70)

    first = client.post("/api/market/advance", json={"days": 3}).json()
    assert first["reached_end"] is False

    last = None
    for _ in range(10):  # the 70-candle series starts at candle 35, so 35 days remain
        last = client.post("/api/market/advance", json={"days": 5}).json()
    assert last["reached_end"] is True
    assert any("end of the real market data" in event for event in last["events"])
    assert client.get("/api/market/status").json()["reached_end"] is True


def test_api_stocks_list_and_prices_only_show_revealed_candles(client, db_session):
    start_market(db_session)
    import_real(db_session)
    warm = market_service.WARMUP_DAYS

    prices = client.get("/api/stocks/REAL/prices").json()
    assert len(prices) == warm
    listed = next(s for s in client.get("/api/stocks").json() if s["symbol"] == "REAL")
    assert listed["current_price"] == prices[-1]["close"]
    assert listed["recent_closes"][-1] == prices[-1]["close"]

    client.post("/api/market/advance", json={"days": 2})
    assert len(client.get("/api/stocks/REAL/prices").json()) == warm + 2


def test_api_reset_replays_real_stocks_from_the_start_and_restores_their_price(client, db_session):
    start_market(db_session)
    stock, candles = import_real(db_session)
    client.post("/api/market/advance", json={"days": 20})

    assert client.post("/api/reset").status_code == 200

    db_session.refresh(stock)
    assert stock.current_price == candles[market_service.WARMUP_DAYS - 1].close
    assert len(client.get("/api/stocks/REAL/prices").json()) == market_service.WARMUP_DAYS
