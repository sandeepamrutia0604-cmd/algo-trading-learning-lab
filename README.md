# Algo Trading Learning Lab

Educational algorithmic trading simulator. Paper-trading only — no real
money, no live orders. See
[algo_trading_learning_lab_project_plan.md](docs/algo_trading_learning_lab_project_plan.md)
for the full phase-by-phase plan.

**Current phase:** Phase 12 - Paper Trading (in progress). First increment: `AngelOneMarketDataAdapter`
is a real implementation — login (client code + PIN + TOTP), the historical candle API, the
scrip-master symbol-to-token mapping, and an LTP quote endpoint, all against Angel One's real
SmartAPI (see "Angel One market data" below for setup and how to import real NSE stocks into
the app), plus a market clock that replays imported real stocks day by day and an optional
slippage/brokerage/tax simulation (see "Trading costs" below). Still to come: live WebSocket
ticks instead of the current REST-poll-based price lookups. No real-money order execution
ever — see Security and Safety Principles.

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
- **Learn** - Learning Mode: ten short lessons (what is a stock, an order, a portfolio, an
  indicator, a strategy, backtesting, risk management, overfitting, paper trading, live
  algorithmic trading), each with an experiment you can run in the simulator. A "Learn" card on
  the Home page shows your progress and a Continue learning button for the next module. Each lesson
  ends with a quiz: wrong answers can be retried, the explanation appears once you get one
  right, and finishing a quiz ticks the module off. Progress is kept in your browser
  (localStorage), not the database. Lesson text is plain data in `frontend/js/learn/lessons.js`,
  rendered by `frontend/js/pages/learn.js`; each lesson has its own link (`#/learn/3`).

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
auto-sells its position if the price closes below the entry minus the stop-loss %. That sized
quantity is then shrunk to fit the max allocation per stock (2% risk with a 5% stop wants 40% of
capital, so the default 20% cap would otherwise reject every buy). Max open
positions and max allocation per stock still apply to every BUY, manual or auto-trade, and
reject a manual or fixed-quantity order that exceeds them. Turn it off
and the app behaves exactly as it did in Phase 4-6 (fixed quantity, no caps, no stop-loss).

Backtests use these same saved risk settings — if risk management is on, a backtest sizes and
stop-losses its trades exactly as live auto-trading would. A buy is skipped (counted in
`skipped_buys`) only if the cap leaves room for less than one share, if cash runs short, or if
a fixed quantity exceeds the cap. `max_open_positions` is the one
setting a backtest can't exercise, since it only ever trades one stock at a time. The shared
formulas live in `backend/app/engine/risk_math.py`, used by both `risk_service.py` (against the
real DB portfolio) and `engine/backtest.py` (against the backtest's own simulated capital), so
the two paths can never drift apart. With risk management off, backtests behave exactly as
before — this is a correctness fix, not a new toggle.

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

Market data adapter (`backend/app/adapters/`): `strategy_service._series()` and
`backtest_service.run()` fetch candles via `get_market_data_adapter(db)` rather than querying
`PriceData` or `market_service` directly. Switch providers with `MARKET_DATA_PROVIDER` in
`.env` (`dummy`, the default, or `angel_one`). "Current price" (used by risk-based position
sizing and the watchlist) still reads `Stock.current_price` directly rather than going through
the adapter — that's a live WebSocket feed, not built yet.

### Angel One market data (real SmartAPI)

`AngelOneMarketDataAdapter` logs into a real Angel One account and serves real NSE candles/LTP
through the same `MarketDataAdapter` interface the dummy simulator uses — nothing downstream
(strategies, backtests, auto-trade) needs to know the difference. It never calls an
order-placement endpoint; this project only ever reads data from Angel One (see Security and
Safety Principles below).

Setup:
1. Register for an API key at the SmartAPI developer portal, and enable TOTP 2FA on your
   Angel One account to get a TOTP secret (the seed key, not a 6-digit code).
2. Fill in `ANGEL_ONE_API_KEY`, `ANGEL_ONE_CLIENT_CODE`, `ANGEL_ONE_PIN` and
   `ANGEL_ONE_TOTP_SECRET` in your own `.env` — never anywhere else, never in Git.
3. Test it directly, without running the full app:
   ```bash
   python scripts/test_angel_one_adapter.py RELIANCE
   ```
   This logs in, resolves `RELIANCE`'s instrument token from the scrip master, and prints its
   latest price and last 10 daily candles, then logs out.
4. Import real stocks into the app's own database:
   ```bash
   python scripts/import_real_stocks.py              # RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK
   python scripts/import_real_stocks.py RELIANCE TCS  # or specific symbols
   ```
   This creates a `Stock` row and real daily candles (`PriceData` rows) for each symbol, the
   same tables the simulator's ALPHA/BETA/GAMMA/DELTA stocks use — so a real stock shows up in
   every existing dropdown (Trade, Strategies, Backtests), chart and the home watchlist with no
   frontend changes. Re-run the script any time to refresh a stock's price history.

   `MARKET_DATA_PROVIDER` stays `dummy` — it isn't involved in this path and doesn't need to be
   flipped. Each `Stock` row has a `source` column (`"simulated"` or `"angel_one"`); the
   simulator (`market_service.generate_all`/`advance`/`reset_market`, used by "Advance market"
   and "Reset" in the UI) only ever touches `source="simulated"` stocks, so it can never
   overwrite a real stock's imported history.

How it works: `loginByPassword` (client code + PIN + a freshly generated TOTP) returns a JWT
that's reused across requests and proactively refreshed well before SmartAPI's midnight
session expiry (`angel_one_auth.py`); the scrip master (a daily JSON dump of every tradable
instrument) is downloaded once and cached to `data/angel_one_scrip_master.json` for 24 hours
to resolve a trading symbol to the instrument token SmartAPI's data endpoints expect
(`scrip_master.py`); historical candles are cached in memory for 60 seconds and both the
candle and LTP endpoints are throttled to stay under SmartAPI's published per-second rate
limits (`angel_one.py`) — the adapter is a natural place for that caching since every caller
goes through it rather than hitting the API directly.

### Upstox market data (a simpler token)

`UpstoxMarketDataAdapter` reads real NSE daily candles with an Upstox **Analytics Token**: a free,
read-only token that lasts a year and needs no static IP for market data. It can't place orders,
and this project never tries to. Compared with Angel One it needs one value instead of four (no
client code, PIN or TOTP), and it can return up to 10 years of daily history in one request.

Setup:
1. On Upstox's Developer Apps page, open the **Analytics** tab and click Generate Token.
2. Put it in your own `.env` as `UPSTOX_ANALYTICS_TOKEN=...` -- never in `.env.example` (which
   git tracks), never in chat, never committed.
3. Test it directly: `python scripts/test_upstox_adapter.py RELIANCE`
4. Import stocks into the database, the same way as for Angel One:
   ```bash
   python scripts/import_real_stocks.py --source upstox                       # the default list, 5 years
   python scripts/import_real_stocks.py --source upstox --years 8 RELIANCE TCS
   python scripts/import_real_stocks.py --source upstox --merge INFY           # keep older history
   ```

The candles are written to the same `Stock`/`PriceData` tables as every other stock (marked
`source="upstox"`), so they survive restarts, replay on the market clock, and work in charts,
trading and backtests. By default an import *replaces* a stock's stored history with what Upstox
returns; `--merge` merges by date instead, which keeps anything Upstox didn't return (for
example years you imported from a CSV). Each stock is imported on its own, so one unknown
symbol is reported without stopping the rest.

How it works: Upstox identifies a stock by an instrument key such as `NSE_EQ|INE002A01018`, not
its symbol. Its public daily instrument file maps each symbol to a key; the adapter caches the
~2,900 cash-equity rows to `data/upstox_nse_instruments.json` for 24 hours (gitignored). Candles
come from `GET /v3/historical-candle/{key}/days/1/{to}/{from}` with the token as a bearer
header. Both the file layout and the endpoint were checked against Upstox's docs and its real
instrument file. `MARKET_DATA_PROVIDER=upstox` also works, like `angel_one`, but the import
above is the usual route.

### Adding stocks from the app: Trade, then Import data

The **Import data** tab on the Trade page has an **Import from** choice: *A file (CSV)*, *Upstox* or
*Angel One*. For a broker, type plain NSE symbols (`SBIN, WIPRO, INFY`, up to 25 at a time), pick
the years of history (Upstox: 1 to 10, default 5; Angel One gives about 400 days), and press
Import. Each stock is fetched and stored on its own, so one unknown symbol is reported without
stopping the rest, and the result list shows what was stored for each (company name, candle
count, date range, price). New stocks appear in every dropdown straight away and replay on the
market clock like the others.

The tab first shows whether the chosen broker is set up. If not, it names the `.env` settings
still missing (names only, never values); add them to your local `.env` and press *check again*
-- the app re-reads `.env` on each check, so no restart is needed. Your credentials are only ever
read by the server and are never typed into the page or sent to it. By default a stock you
already have is **replaced** by the broker's history (the page asks first); tick *Keep existing
history (merge)* to keep anything the broker doesn't return. A rejected Upstox token stops the
batch with a clear message instead of failing every symbol the same way. The command-line
script and this screen share one code path (`services/data_sources.py`), so they behave alike.

### Importing market data from a file (no credentials)

If you'd rather not put broker credentials in `.env` at all, download daily candles yourself
(a broker's chatbot table, a TradingView/Yahoo/NSE export) and import the file. In the app, use
**Trade → Import data** (pick the file, enter the symbol, press Import). Or from the command line:

```bash
python scripts/import_csv.py RELIANCE path/to/reliance.csv --name "Reliance Industries"
```

The first row must name the columns (Date, Open, High, Low, Close, Volume; volume is optional).
Tab, comma or semicolon delimiters, dates like `01 Oct 2026` / `2026-10-01` / `01/10/2026`
(day first), thousands separators (`1,180.1`) and newest-first row order are all handled. A
row that can't be read stops the import with its line number rather than being skipped.

By default the file is **merged** into the stock's existing history by date, so a short file
adds its days without losing the rest; `--replace` discards the old history first. Simulated
stocks (ALPHA/BETA/GAMMA/DELTA) are refused. Imported stocks get `source="csv"`, so the
simulator never touches them, and they work in charts, trading, strategies and backtests
exactly like the Angel One ones. Like those, the data is a snapshot: re-import to bring it up to date.

### How imported stocks replay (the market clock)

The app keeps one **market clock** (`Portfolio.market_date`), the simulated "today", and every
stock only shows candles up to it. An imported stock's whole real history is stored, but only
its first ~60 days are showing when the market starts; each **+1 day / +5 days / Play** moves the
clock forward one business day, revealing that day's real candle (chart, price, watchlist,
sparklines, portfolio value and equity curve all follow). The simulated stocks generate their
next day on the same clock, so everything shares one calendar. When the real data runs out,
the clock stops (Play stops itself with a message) and **Reset** replays it from the start.

Things worth knowing:
- Charts, signals, auto-trading and the equity curve see only what has "happened" by the clock,
  so a strategy can't trade on candles from its own future. **Backtests are the exception**:
  they analyse the stock's whole stored history regardless of the clock.
- Importing a stock whose history is entirely after the clock moves the clock up to where it
  has warm-up history showing (and extends the simulated stocks to match); history that is
  already in the past just appears. The clock never moves backwards except on Reset.
- If the real data ends before the clock, nothing is being replayed, so advancing carries on
  for the simulated stocks (the real stock's price simply holds at its last candle).
- Databases from before the clock existed pick one up on the next startup, without losing
  anything.

### Trading costs: slippage, brokerage and taxes

Trade → **Trading costs** tab (off by default). With it on, every paper trade, auto-trade and
backtest pays what a real account would:

- **Slippage** — you rarely get the exact quote. A BUY fills a little above it and a SELL a
  little below, by a % of the price (default 0.05%).
- **Brokerage** — a % of the trade value, optionally capped at a flat amount per order, the way
  discount brokers price (default 0.03%, capped at ₹20).
- **Taxes and levies** — one flat % of the trade value (default 0.1%). This is an educational
  approximation, not an exact STT/GST/stamp-duty calculation; check your broker's contract
  note for real numbers.

How it's accounted: a trade's price is the fill price (the quote it was based on is kept as
`market_price`), charges come out of cash and are recorded as the trade's `fees`, and a
position's average price is its cost basis *including* the buy-side charges, so a sale's
realized P&L is net of everything paid to get in and out. The order ticket previews the fill
price, the charges and the cash left. Backtests use the same saved settings and report
"Charges paid" and "Slippage cost" alongside the result; a strategy that looks profitable
before costs often isn't after them, which is the point. The formulas live in
`backend/app/engine/cost_math.py`, shared by `trading_service.py` and `engine/backtest.py` the
same way the risk formulas are, so a backtest pays exactly what a live paper trade would.

### What backtests still don't model

Position sizing, available capital, stop-loss, max allocation, no-look-ahead, and (when switched
on) slippage, brokerage and taxes are all accounted for (see above). Not yet modeled, by
design — these are slated for Phase 13 (Advanced Topics): whether you could really have traded
the size you wanted at that price (market impact and liquidity, partial fills), and corporate
actions (splits, dividends, bonus issues), which matter for real listed stocks but don't apply
to the synthetic ALPHA/BETA/GAMMA/DELTA.

## Test

```bash
pytest
```

The Learn page's lesson data and progress logic have their own tests (Node 18+, no install needed):

```bash
node --test frontend/js/learn/lessons.test.mjs
```

They check that every written lesson is well formed and that every quiz answer points at a real
option, which matters as lessons are added.

## Project Structure

```text
backend/
  app/
    main.py        FastAPI app + static frontend mount
    config.py       Settings loaded from .env
    db.py           SQLAlchemy engine/session (SQLite for now)
    logging_config.py
    api/            Route handlers
    adapters/       MarketDataAdapter interface (base.py); dummy.py (today's default);
                    angel_one.py + angel_one_auth.py + scrip_master.py (real SmartAPI client);
                    upstox.py (Upstox Analytics Token client); rate_limiter.py (shared throttle);
                    csv_candles.py (CSV/TSV candle parser for file imports);
                    get_market_data_adapter() picks one by MARKET_DATA_PROVIDER
    models/         SQLAlchemy models (Stock, Portfolio, Position, Trade,
                    PriceData, MarketConfig, Strategy, Signal, RiskSettings)
    schemas.py      Pydantic request/response models
    services/       Trading logic, portfolio math, market/price history, seeding,
                    risk_service.py (position sizing, stop-loss, exposure caps),
                    cost_service.py (saved slippage/brokerage/tax settings),
                    analytics_service.py (trade stats, drawdown, Sharpe, monthly returns),
                    real_stocks.py (imports a real symbol's history into Stock/PriceData)
    strategies/     One pure module per canned strategy type + registry.py
    engine/         price_models.py, indicators.py, backtest.py, rule_engine.py,
                    risk_math.py + cost_math.py (formulas shared by live trading and backtests)
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
scripts/
  start.bat             Double-click launcher
  test_angel_one_adapter.py   Smoke-tests the real Angel One adapter against your own account
  test_upstox_adapter.py      Smoke-tests the Upstox adapter with your own Analytics Token
  import_real_stocks.py       Imports real NSE stocks + history (--source angel_one or upstox) into the app's database
  import_csv.py               Imports a stock's candles from a CSV/TSV file (no credentials)
data/               SQLite database file + cached Angel One scrip master (gitignored)
```
