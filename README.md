# Algo Trading Learning Lab

Educational algorithmic trading simulator. Paper-trading only — no real
money, no live orders. See
[algo_trading_learning_lab_project_plan.md](docs/algo_trading_learning_lab_project_plan.md)
for the full phase-by-phase plan.

**Current phase:** Phase 3 — Trading Dashboard (candlestick chart with
moving-average overlays and BUY/SELL markers, positions, trade history with
realized P&L).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env
```

## Run

```bash
uvicorn backend.app.main:app --reload
```

Open http://127.0.0.1:8000 — you should see your ₹1,00,000 virtual
wallet, a candlestick chart, four dummy stocks (ALPHA/BETA/GAMMA/DELTA),
and be able to advance the market day by day (or press Play), change each
stock's price model, buy/sell, and reset the simulation.

Chart: tick Fast/Slow SMA (any period 2-500) to overlay moving averages,
and "Show my trades" to plot your BUY/SELL markers. Click any stock symbol
in the Stocks or Positions tables to switch the chart to it.

Price models: random walk, trending (momentum), volatile (~2.5x swings),
sideways (mean-reverting). Changing a stock's model applies to newly
generated days ("Advance" or "Regenerate history"), not past candles.

## Test

```bash
pytest
```

## Project Structure

```text
backend/
  app/
    main.py        FastAPI app + static frontend mount
    config.py       Settings loaded from .env
    db.py           SQLAlchemy engine/session (SQLite for now)
    logging_config.py
    api/            Route handlers
    models/         SQLAlchemy models (Stock, Portfolio, Position, Trade,
                    PriceData, MarketConfig)
    schemas.py      Pydantic request/response models
    services/       Trading logic, portfolio math, market/price history, seeding
    strategies/      Strategy implementations (Phase 4+)
    engine/         price_models.py, indicators.py (pure, no DB); backtesting from Phase 6
    migrations.py   Adds new columns to databases created by earlier phases
    risk/           Risk management (Phase 7+)
  tests/
frontend/
  index.html, css/, js/
data/               SQLite database file (gitignored)
```
