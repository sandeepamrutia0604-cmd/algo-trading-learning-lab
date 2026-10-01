# Algo Trading Learning Lab

Educational algorithmic trading simulator. Paper-trading only — no real
money, no live orders. See
[algo_trading_learning_lab_project_plan.md](docs/algo_trading_learning_lab_project_plan.md)
for the full phase-by-phase plan.

**Current phase:** Phase 10 - Strategy Comparison: on the Backtests page, run any mix of
strategy types on the same stock's history and add each result to a side-by-side comparison —
initial/final capital, return, trades, win rate and max drawdown in one table, plus an overlaid
equity-curve chart. Measurements only, not a recommendation for real money.

Screens (left navigation):
- **Home** - portfolio hero with equity curve, practice checklist, watchlist, recent trades.
- **Trade** - the terminal: watchlist, candlestick chart with SMA overlays, your BUY/SELL
  markers and strategy signals, order ticket, and a bottom panel for positions, trades,
  market settings and risk management.
- **Strategies** - the lab. Pick a type, tune its parameters, press "Run on history" to mark
  every signal on the chart with its indicators, or turn on auto-trade to place paper trades
  as the market advances. "Try one of each on this stock" creates all six so you can compare.
  Pick "Custom" to build your own entry/exit conditions instead.
- **Backtests** - pick a type and starting capital, press "Run backtest" to replay it over
  history: final capital, return, trade count, win rate, max drawdown, an equity curve against
  buy-and-hold, and every simulated trade. Add a result to the strategy comparison table to
  weigh it against other runs on the same stock. Nothing here touches your real paper portfolio.
- **Performance** - the analytics dashboard for your actual paper trades (see above).
- **Journal** - a feed of every signal with its reasons and outcome.
- **Learn** - placeholder for a later phase.

Strategy types (all long-only: one position at a time, signals never look ahead):
- **MA Crossover** - fast SMA crosses above/below slow SMA. Best in trends; whipsaws in sideways markets.
- **RSI** - buy when RSI falls below the oversold line, sell above the overbought line.
- **Bollinger Bands** - buy below the lower band, sell above the upper band.
- **Breakout** - buy a new N-day high, exit below the M-day low.
- **Mean Reversion** - buy when the z-score vs the average is very low, sell back at the average.
- **Combined** - a crossover that only buys if RSI, price and volatility checks also pass.

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

Every response (API and static frontend files) is sent with `Cache-Control: no-store`, since this
is a local single-user app with fast-changing state and files that get edited during development —
your browser should never show stale data or a stale script after a change.

A signal on a given day only uses prices up to that day (no look-ahead). Auto-trade advances the
market one day at a time so each signal trades at its own day's close. To add a strategy type,
create a module in backend/app/strategies/ that defines a StrategyDef and register it in registry.py;
the builder form, API, chart overlays and "Why" cards pick it up automatically.

Risk management (Trade → Risk management tab, off by default): with it on, an auto-trade
strategy's BUY is sized from your risk per trade and stop-loss (`capital × risk% ÷ (price × stop%)`,
same formula as the plan's worked example) instead of its fixed quantity, and a stop-loss
auto-sells its position if the price closes below the entry minus the stop-loss %. Max open
positions and max allocation per stock apply to every BUY, manual or auto-trade. Turn it off
and the app behaves exactly as it did in Phase 4-6 (fixed quantity, no caps, no stop-loss).

Price models: random walk, trending (momentum), volatile (~2.5x swings),
sideways (mean-reverting). Changing a stock's model applies to newly
generated days ("Advance" or "Regenerate history"), not past candles.

Performance analytics are computed from your closed (SELL) paper trades and the real equity
curve: profit factor and average win/loss come from realized P&L per trade, max drawdown and
Sharpe ratio (annualized, 0% risk-free rate) come from the day-by-day portfolio value, and the
strategy comparison table groups trades by whichever strategy placed them (or "Manual").

Custom strategies: entry is one side (all AND, or any OR) of conditions like "SMA(20) crosses
above SMA(50)" or "RSI(14) < 30"; exit works the same way. A custom strategy plugs into the same
signals/chart/auto-trade/backtest pipeline as the six canned types — it just builds its
StrategyDef from your condition tree (backend/app/engine/rule_engine.py) instead of Python code.
For a stop-loss exit, use the Risk management tab rather than a condition.

Strategy comparison (Backtests page) is purely a frontend feature: every "Add to comparison"
click just keeps that backtest's result in the browser (up to 6 at a time), so comparing several
strategies is really running `/api/backtests/run` several times against the same stock's price
history — no separate backend endpoint or persistence.

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
                    PriceData, MarketConfig, Strategy, Signal, RiskSettings)
    schemas.py      Pydantic request/response models
    services/       Trading logic, portfolio math, market/price history, seeding,
                    risk_service.py (position sizing, stop-loss, exposure caps),
                    analytics_service.py (trade stats, drawdown, Sharpe, monthly returns)
    strategies/     One pure module per canned strategy type + registry.py
    engine/         price_models.py, indicators.py, backtest.py, rule_engine.py
                    (custom entry/exit condition trees -> StrategyDef; all pure, no DB)
    migrations.py   Adds new columns to databases created by earlier phases
  tests/
frontend/
  index.html      App shell (sidebar, top bar, page sections)
  css/style.css   Dark/light theme tokens and layout
  js/             ES modules: app.js (router), store.js, topbar.js, theme.js, util.js,
                  chart.js (shared price chart), why.js (the "Why?" card),
                  rulebuilder.js (custom-strategy condition editor)
  js/pages/       home.js, trade.js, strategies.js, backtests.js, performance.js, journal.js, soon.js
data/               SQLite database file (gitignored)
```
