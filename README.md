# Algo Trading Learning Lab

Educational algorithmic trading simulator. Paper-trading only — no real
money, no live orders. See
[algo_trading_learning_lab_project_plan.md](docs/algo_trading_learning_lab_project_plan.md)
for the full phase-by-phase plan.

**Current phase:** Phase 3 dashboard, redesigned as a multi-screen app with a
dark trading-terminal theme (light theme toggle in the sidebar).

Screens (left navigation):
- **Home** — portfolio hero with equity curve, practice checklist, watchlist, recent trades.
- **Trade** — the terminal: watchlist, candlestick chart with SMA overlays and BUY/SELL
  markers, order ticket, and a bottom panel for positions, trades and market settings.
- **Strategies / Backtests / Compare / Journal / Learn** — placeholders for later phases.

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

Chart: tick the two SMA chips (any period 2-500) to overlay moving averages,
and "My trades" to plot your BUY/SELL markers. Click a stock in the watchlist
to switch the chart and order ticket to it. The market controls (+1 day, +5 days,
Play, speed, Reset) are in the top bar on every screen.

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
  index.html      App shell (sidebar, top bar, page sections)
  css/style.css   Dark/light theme tokens and layout
  js/             ES modules: app.js (router), store.js, topbar.js, theme.js, util.js
  js/pages/       home.js, trade.js, soon.js
data/               SQLite database file (gitignored)
```
