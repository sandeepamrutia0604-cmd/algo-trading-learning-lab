from sqlalchemy import Engine, inspect, text

# Columns added after a table first shipped. create_all() never alters existing tables,
# so databases created by an earlier phase get these added on startup.
ADDED_COLUMNS = {
    "trades": {"market_date": "DATE", "realized_pnl": "FLOAT", "strategy_id": "INTEGER"},
    "strategies": {"rules": "JSON"},
    "stocks": {"source": "VARCHAR(20) DEFAULT 'simulated'"},
}


def ensure_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    for table, columns in ADDED_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        with engine.begin() as conn:
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
