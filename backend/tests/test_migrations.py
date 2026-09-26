from sqlalchemy import create_engine, inspect, text

from backend.app.migrations import ensure_columns


def test_ensure_columns_upgrades_old_trades_table_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE trades (id INTEGER PRIMARY KEY, side VARCHAR(4))"))
        conn.execute(text("INSERT INTO trades (side) VALUES ('BUY')"))

    ensure_columns(engine)
    ensure_columns(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("trades")}
    assert {"market_date", "realized_pnl", "strategy_id"} <= columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT market_date, realized_pnl FROM trades")).fetchall() == [(None, None)]


def test_ensure_columns_ignores_missing_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    ensure_columns(engine)
