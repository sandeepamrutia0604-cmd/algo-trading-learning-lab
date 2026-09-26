# Algo Trading Learning Lab

Educational algorithmic trading simulator. Paper-trading only — no real
money, no live orders. See
[algo_trading_learning_lab_project_plan.md](docs/algo_trading_learning_lab_project_plan.md)
for the full phase-by-phase plan.

**Current phase:** Phase 1 — Basic Trading Simulator (virtual wallet,
dummy stocks, manual buy/sell, positions, trade history, reset).

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
wallet, four dummy stocks (ALPHA/BETA/GAMMA/DELTA), and be able to buy,
sell, and reset the simulation.

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
    models/         SQLAlchemy models (Stock, Portfolio, Position, Trade)
    schemas.py      Pydantic request/response models
    services/       Trading logic, portfolio math, seeding
    strategies/      Strategy implementations (Phase 4+)
    engine/         Backtesting/simulation engine (Phase 6+)
    risk/           Risk management (Phase 7+)
  tests/
frontend/
  index.html, css/, js/
data/               SQLite database file (gitignored)
```
