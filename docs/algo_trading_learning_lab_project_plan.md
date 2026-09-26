# Algo Trading Learning Lab

## Phase-Wise Project Plan

**Project Type:** Educational algorithmic trading simulator\
**Primary Goal:** Learn algo-trading fundamentals by building a safe
paper-trading environment using dummy stocks and virtual money.

> **Important:** This project is intended for education and simulation.
> Initial phases must not place real trades or use real money.

------------------------------------------------------------------------

# 1. Project Vision

Build a web-based **Algo Trading Learning Lab** where a user can:

-   Create and manage dummy stocks.
-   Generate or import simulated price data.
-   Start with virtual cash.
-   Manually buy and sell dummy stocks.
-   Create trading strategies using simple rules.
-   Run strategies automatically.
-   Backtest strategies against historical/simulated data.
-   Understand why a strategy generated a BUY/SELL/HOLD signal.
-   Measure portfolio performance and risk.
-   Progressively move from simple trading concepts to more advanced
    algorithmic strategies.

The application should behave like a small trading laboratory rather
than a real-money trading platform.

------------------------------------------------------------------------

# 2. High-Level Architecture

``` text
                         ┌──────────────────────┐
                         │      Web Dashboard   │
                         │  Charts / Controls   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       API Layer      │
                         │       FastAPI        │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
        ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
        │ Price Engine   │ │ Strategy Engine│ │  Risk Engine   │
        │ Dummy Prices   │ │ BUY/SELL Rules │ │ Position Size  │
        └───────┬────────┘ └───────┬────────┘ └───────┬────────┘
                │                  │                  │
                └──────────────────┼──────────────────┘
                                   ▼
                         ┌──────────────────────┐
                         │   Trading Simulator  │
                         │ Orders / Portfolio   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       SQLite DB      │
                         │ Prices / Trades /    │
                         │ Portfolio / Strategies│
                         └──────────────────────┘
```

------------------------------------------------------------------------

# 3. Suggested Technology Stack

## Backend

-   Python
-   FastAPI
-   Pydantic
-   Pandas
-   NumPy

## Frontend

### Initial version

-   HTML
-   CSS
-   JavaScript
-   Plotly.js

### Later option

-   React
-   TypeScript

## Database

-   SQLite for the learning version
-   PostgreSQL if the project later becomes multi-user

## Testing

-   pytest
-   API tests
-   Strategy unit tests
-   Backtesting validation tests

## Deployment

Initial:

``` text
Local PC
   ↓
Python virtual environment
   ↓
FastAPI
   ↓
Browser
```

Later:

``` text
Browser
   ↓
Reverse Proxy
   ↓
FastAPI
   ↓
Database
```

------------------------------------------------------------------------

# 4. Development Cycle & Timeline Planning

## Why This Section Exists

You don't yet know how much work this will take, and that's normal --- the
phases below were written before any code exists, so their true size is
still a guess. Rather than pretending to know a calendar timeline, plan the
project the way real software teams do: **estimate relative size, build in
small iterations, measure your actual pace, then re-forecast.**

## Development Cycle (repeat this per phase)

``` text
Plan
  ↓
Build (smallest usable slice first)
  ↓
Test (unit + manual click-through)
  ↓
Check against that phase's Learning Outcome / Definition of Done
  ↓
Retro: what took longer than expected? what would you cut next time?
  ↓
Re-estimate remaining phases using what you just learned
  ↓
Next phase
```

Do not start a new phase until the current one's checklist is genuinely
done. A half-finished Phase 4 makes Phase 5 harder to estimate, not easier.

## Relative Effort, Not Calendar Time

Each phase below is tagged with a relative size instead of a fixed
duration:

``` text
S  = Small   - a focused single session
M  = Medium  - straightforward but has a few moving parts
L  = Large   - real design decisions, worth planning before coding
XL = Extra Large - external dependencies, async data, or open-ended scope
```

Sizes compound: an "L" after several "M" phases usually takes longer than
an "L" attempted first, because you're also maintaining everything already
built. Treat the sizes as *relative to each other*, not as promises.

## How to Turn Sizes Into Your Own Timeline

1.  **Build Phase 0 and Phase 1 first** (both tagged S). Track how many
    real hours they actually took you.
2.  **Use that as your calibration.** If Phase 0 + Phase 1 took you ~6
    hours combined, a rough personal scale is: S ≈ that pace, M ≈ 2--3x an
    S, L ≈ 2--3x an M, XL ≈ open-ended (budget a review checkpoint rather
    than an end date).
3.  **Re-forecast after every MVP milestone** (after V1, after V2, after
    V3 --- see §27 Recommended MVP), not just once at the start. Your pace
    will change as the codebase grows.
4.  **Treat Phase 13 (Advanced Topics) and Phase 12 (Paper Trading) as
    open-ended.** They depend on an external broker API (Angel One) and
    on topics you'll only fully understand once you reach them. Don't put
    a date on them --- put a "ready to start" condition instead (e.g. "start
    Phase 12 once Phase 6 backtest results look trustworthy").

## Signal to Descope Further

If a phase is taking noticeably longer than its size tag suggests relative
to Phase 0/1, that's not a scheduling problem to push through --- it's a
signal the phase is bigger than it looks. Cut it down (fewer strategies in
Phase 5, fewer metrics in Phase 8, etc.) rather than extending the
deadline. The MVP staging in §27 exists exactly so you always have a
working, demoable app even if later phases slip.

------------------------------------------------------------------------

# 5. Phase 0 --- Project Foundation

**Relative Effort:** Small (S)

## Objective

Create the basic project structure and development environment.

## Tasks

-   Create Git repository.
-   Create Python virtual environment.
-   Set up FastAPI.
-   Set up frontend.
-   Configure SQLite.
-   Add configuration management.
-   Add logging.
-   Create initial API health endpoint.
-   Create basic dashboard shell.

## Suggested Structure

``` text
algo-trading-lab/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   ├── strategies/
│   │   ├── engine/
│   │   └── risk/
│   │
│   └── tests/
│
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/
│
├── data/
├── docs/
├── scripts/
├── requirements.txt
├── README.md
└── .gitignore
```

## Learning Outcome

Understand:

-   Python project structure
-   REST APIs
-   FastAPI
-   SQLite
-   Frontend/backend communication

------------------------------------------------------------------------

# 6. Phase 1 --- Basic Trading Simulator

**Relative Effort:** Small (S)

## Objective

Learn the fundamental mechanics of buying and selling shares.

## Features

### Virtual Wallet

Start with:

``` text
Virtual Capital: ₹1,00,000
```

Display:

-   Available cash
-   Invested amount
-   Portfolio value
-   Total P&L

### Dummy Stocks

Example:

  Symbol   Name                  Starting Price
  -------- ------------------- ----------------
  ALPHA    Alpha Industries                ₹100
  BETA     Beta Technologies               ₹250
  GAMMA    Gamma Foods                      ₹75
  DELTA    Delta Motors                    ₹500

### Manual Trading

Provide:

``` text
BUY
SELL
```

Inputs:

-   Stock
-   Quantity
-   Price
-   Order type

## Trade Model

``` text
BUY ALPHA
Price: ₹100
Quantity: 100

Cost = ₹10,000
```

Wallet:

``` text
Before: ₹1,00,000
After:  ₹90,000
```

## Learning Outcome

Understand:

-   Shares
-   Price
-   Quantity
-   Orders
-   Positions
-   Cash balance
-   Portfolio value
-   Realized P&L
-   Unrealized P&L

------------------------------------------------------------------------

# 7. Phase 2 --- Dummy Price Engine

**Relative Effort:** Medium (M)

## Objective

Create a simulated market so prices change automatically.

## Features

Generate price movements using configurable models.

Example:

``` text
Day 1  ₹100
Day 2  ₹102
Day 3  ₹101
Day 4  ₹105
Day 5  ₹108
```

## Price Models

### Random Walk

Simple random price movement.

### Trending Market

Price gradually moves upward or downward.

### Volatile Market

Larger random movements.

### Sideways Market

Price moves within a range.

## Market Controls

Allow the user to configure:

``` text
Initial Price
Volatility
Trend
Market Speed
Number of Trading Days
```

## Learning Outcome

Understand:

-   OHLC data
-   Candles
-   Price movement
-   Volatility
-   Trends
-   Market regimes

------------------------------------------------------------------------

# 8. Phase 3 --- Trading Dashboard

**Relative Effort:** Medium (M)

## Objective

Build the main learning dashboard.

## Dashboard Components

### Portfolio Summary

``` text
Cash                 ₹82,450
Invested             ₹17,550
Portfolio Value      ₹1,04,300
Total P&L             ₹4,300
Return                   4.30%
```

### Stock Chart

Display:

-   Price
-   Moving averages
-   BUY markers
-   SELL markers

### Positions

``` text
ALPHA
100 shares
Average Price: ₹100
Current Price: ₹108
P&L: +₹800
```

### Trade History

``` text
Time       Symbol   Action   Price   Qty
09:30      ALPHA    BUY      100     100
11:45      ALPHA    SELL     108     100
```

## Learning Outcome

Understand how trading activity becomes portfolio performance.

------------------------------------------------------------------------

# 9. Phase 4 --- First Algorithm: Moving Average Crossover

**Relative Effort:** Medium (M)

## Objective

Introduce algorithmic trading.

## Strategy

Calculate:

``` text
Fast Moving Average = 20 days
Slow Moving Average = 50 days
```

Rules:

``` text
Fast MA crosses ABOVE Slow MA
        ↓
      BUY
```

``` text
Fast MA crosses BELOW Slow MA
        ↓
      SELL
```

## Dashboard

Allow:

``` text
Fast MA:  [20]
Slow MA:  [50]

[Run Strategy]
```

Show signals directly on the chart.

## Signal Explanation

When a trade occurs:

``` text
BUY SIGNAL

Reason:
20-day MA crossed above 50-day MA.

Price: ₹124.50
```

## Learning Outcome

Understand:

-   Indicators
-   Signals
-   Strategy rules
-   Automated decisions
-   Entry/exit logic

------------------------------------------------------------------------

# 10. Phase 5 --- Strategy Laboratory

**Relative Effort:** Large (L)

## Objective

Allow users to experiment with multiple strategies.

## Strategies

### Strategy 1

Moving Average Crossover

### Strategy 2

RSI

Example educational rule:

``` text
RSI < 30 → BUY signal
RSI > 70 → SELL signal
```

### Strategy 3

Bollinger Bands

Learn:

-   Upper band
-   Middle band
-   Lower band

### Strategy 4

Breakout

Example:

``` text
Current price > previous 20-day high
→ BUY
```

### Strategy 5

Mean Reversion

### Strategy 6

Combined Strategy

Example:

``` text
MA crossover
+
RSI confirmation
+
Risk filter
```

## Learning Outcome

Understand that different strategies behave differently under different
market conditions.

------------------------------------------------------------------------

# 11. Phase 6 --- Backtesting Engine

**Relative Effort:** Large (L)

## Objective

Run a strategy over historical or simulated data.

## Example

``` text
Initial Capital: ₹1,00,000

Strategy:
20/50 Moving Average

Period:
500 trading days
```

Output:

``` text
Final Capital       ₹1,14,250
Total Return            14.25%

Total Trades               18
Winning Trades              11
Losing Trades                7

Maximum Drawdown            6.8%
```

## Backtest Rules

The engine must:

1.  Process data chronologically.
2.  Generate signals.
3.  Execute simulated orders.
4.  Update cash.
5.  Update positions.
6.  Calculate portfolio value.
7.  Record every trade.
8.  Calculate performance metrics.

## Important

Avoid look-ahead bias.

A strategy must only use information that would actually have been
available at the time of the decision.

## Learning Outcome

Understand:

-   Historical testing
-   Strategy performance
-   Trade statistics
-   Look-ahead bias
-   Overfitting

------------------------------------------------------------------------

# 12. Phase 7 --- Risk Management

**Relative Effort:** Medium (M)

## Objective

Teach that strategy signals alone are not enough.

## Features

### Maximum Risk Per Trade

Example:

``` text
Capital = ₹1,00,000
Risk = 2%

Maximum risk = ₹2,000
```

### Stop Loss

Example:

``` text
Entry = ₹100
Stop Loss = ₹95
Risk per share = ₹5
```

Position size:

``` text
₹2,000 / ₹5
= 400 shares
```

### Maximum Positions

Example:

``` text
Maximum open positions = 5
```

### Maximum Capital Allocation

Example:

``` text
Maximum allocation per stock = 20%
```

## Learning Outcome

Understand:

-   Stop loss
-   Position sizing
-   Portfolio exposure
-   Risk/reward
-   Capital preservation

------------------------------------------------------------------------

# 13. Phase 8 --- Performance Analytics

**Relative Effort:** Large (L)

## Objective

Create professional-style performance analytics.

## Metrics

### Return

``` text
Total Return %
```

### Win Rate

``` text
Winning Trades / Total Trades
```

### Average Win

``` text
Average profit of winning trades
```

### Average Loss

``` text
Average loss of losing trades
```

### Maximum Drawdown

Measure the largest decline from a portfolio peak.

### Profit Factor

``` text
Gross Profit / Gross Loss
```

### Sharpe Ratio

Introduce the concept of risk-adjusted return.

## Dashboard

Create:

-   Equity curve
-   Drawdown chart
-   Monthly returns
-   Trade distribution
-   Winning vs losing trades
-   Strategy comparison

## Learning Outcome

Learn why simply looking at total profit is not enough.

------------------------------------------------------------------------

# 14. Phase 9 --- Strategy Builder

**Relative Effort:** Large (L)

## Objective

Allow users to create strategies without changing Python code.

Example:

``` text
IF

20 MA crosses above 50 MA

AND

RSI < 70

AND

Price > 100

THEN

BUY
```

Exit:

``` text
IF

20 MA crosses below 50 MA

OR

Stop Loss = 5%

THEN

SELL
```

## UI Concept

``` text
Indicator       Operator       Value
------------------------------------------------
20 MA           crosses above  50 MA

AND

RSI             <               70

AND

Price           >               ₹100

Action:
BUY
```

## Learning Outcome

Understand how trading strategies are essentially sets of rules.

------------------------------------------------------------------------

# 15. Phase 10 --- Strategy Comparison

**Relative Effort:** Medium (M)

## Objective

Compare strategies using the same dataset.

Example:

  Metric              MA Crossover      RSI   Breakout
  ----------------- -------------- -------- ----------
  Initial Capital              ₹1L      ₹1L        ₹1L
  Final Capital             ₹1.14L   ₹1.09L     ₹1.18L
  Trades                        18       32         24
  Win Rate                     61%      53%        58%
  Max Drawdown                6.8%     8.4%      10.1%

The application should present these as factual measurements from the
selected backtest, not as a recommendation about which strategy should
be used with real money.

## Learning Outcome

Understand:

-   Trade-offs
-   Risk vs return
-   Strategy characteristics
-   Why different strategies behave differently

------------------------------------------------------------------------

# 16. Phase 11 --- Market Data Adapter

**Relative Effort:** Large (L)

## Objective

Separate the simulator from the data source.

The application should support:

``` text
Dummy Data
     ↓
Market Data Adapter
     ↓
Strategy Engine
```

Later:

``` text
Angel One (SmartAPI)
     ↓
Market Data Adapter
     ↓
Strategy Engine
     ↓
Paper Trading
```

## Design Principle

The strategy engine should not care where the price data came from.

This makes it possible to change data providers later without rewriting
the strategies.

## Angel One (SmartAPI) Specifics

Since you already have an Angel One account, this is the concrete
provider to build the adapter against:

-   **Historical candle API** --- backfills OHLC data for backtesting
    (Phase 6) once you move past dummy prices.
-   **Instrument master (scrip master) file** --- Angel One publishes a
    JSON list of tradable symbols and their tokens; you'll need to map
    your dummy `stocks` table's `symbol` to Angel One's instrument token
    for any real symbol you add.
-   **WebSocket feed** --- used later in Phase 12 for live LTP (last
    traded price) ticks; not needed until then.
-   **Rate limits** --- SmartAPI enforces per-second/per-day request caps;
    the adapter should cache/throttle rather than call the API on every
    UI refresh.

The adapter interface (function signatures, return shape) should be
designed now, but keep the actual Angel One client behind it as a
separate implementation you plug in only when you reach this phase.

------------------------------------------------------------------------

# 17. Phase 12 --- Paper Trading

**Relative Effort:** Extra Large (XL)

## Objective

Move from completely simulated prices to real market data while keeping
trading virtual.

Flow:

``` text
Angel One (SmartAPI)
       ↓
Strategy
       ↓
Signal
       ↓
Paper Order
       ↓
Virtual Portfolio
```

No real-money order execution.

## Features

-   Real-time/near-real-time prices where supported
-   Virtual order execution
-   Slippage simulation
-   Brokerage/fee simulation
-   Order history
-   Portfolio tracking

## Angel One (SmartAPI) Specifics

-   Use the SmartAPI WebSocket feed for live LTP/quote ticks driving the
    strategy engine.
-   **Never call Angel One's real order-placement endpoints in this
    project.** A "paper order" here means: strategy generates a signal →
    your own code books it against the virtual portfolio in your
    database. Angel One is a data source only, never an execution venue,
    until you have deliberately decided to move beyond this learning lab.
-   Login uses an API key + client code + password/PIN + a TOTP secret
    (2FA). Keep all of these out of source control --- see §26 Security
    and Safety Principles.

## Learning Outcome

Understand the difference between:

``` text
Backtesting
     ↓
Simulation
     ↓
Paper Trading
     ↓
Live Trading
```

------------------------------------------------------------------------

# 18. Phase 13 --- Advanced Topics

**Relative Effort:** Extra Large (XL) -- open-ended

Only after the fundamentals are understood.

Possible topics:

-   Multiple timeframes
-   Portfolio strategies
-   Correlation
-   Sector allocation
-   Volatility-based position sizing
-   Transaction costs
-   Slippage
-   Market impact
-   Walk-forward testing
-   Out-of-sample testing
-   Parameter optimization
-   Monte Carlo analysis
-   Machine learning experiments

Machine learning should come later. It is better to understand
conventional strategy logic and proper backtesting first.

------------------------------------------------------------------------

# 19. Educational "Why?" System

A major feature of the application should be the ability to explain
every decision.

For each trade:

``` text
┌───────────────────────────────┐
│        WHY DID I BUY?         │
├───────────────────────────────┤
│ Stock: ALPHA                  │
│ Price: ₹124.50                │
│                               │
│ ✓ 20 MA crossed above 50 MA   │
│ ✓ RSI = 54                    │
│ ✓ Price above 20 MA           │
│                               │
│ Stop Loss: ₹118.28            │
│ Quantity: 300                 │
└───────────────────────────────┘
```

For every signal, store:

-   Timestamp
-   Price
-   Indicator values
-   Strategy rule
-   Signal
-   Position size
-   Risk settings
-   Execution price

This makes the system useful for learning rather than simply producing
BUY/SELL labels.

------------------------------------------------------------------------

# 20. Learning Mode

Add a dedicated learning section.

## Module 1

What is a stock?

## Module 2

What is an order?

## Module 3

What is a portfolio?

## Module 4

What is an indicator?

## Module 5

What is a trading strategy?

## Module 6

What is backtesting?

## Module 7

What is risk management?

## Module 8

What is overfitting?

## Module 9

What is paper trading?

## Module 10

What is live algorithmic trading?

Each lesson can include:

-   Short explanation
-   Example
-   Interactive exercise
-   Quiz
-   Practical experiment

------------------------------------------------------------------------

# 21. Suggested User Journey

The application should guide the learner through this progression:

``` text
START
  │
  ▼
Learn Trading Basics
  │
  ▼
Create Dummy Stock
  │
  ▼
Receive ₹1,00,000 Virtual Cash
  │
  ▼
Manually Buy/Sell
  │
  ▼
Understand P&L
  │
  ▼
Learn Indicators
  │
  ▼
Create First Strategy
  │
  ▼
Generate BUY/SELL Signals
  │
  ▼
Backtest Strategy
  │
  ▼
Add Risk Management
  │
  ▼
Analyze Performance
  │
  ▼
Compare Strategies
  │
  ▼
Paper Trading
  │
  ▼
Advanced Topics
```

------------------------------------------------------------------------

# 22. Database Design

Initial tables:

## stocks

``` text
id
symbol
name
starting_price
created_at
```

## price_data

``` text
id
stock_id
timestamp
open
high
low
close
volume
```

> **Note:** This is a single-user local application --- there's no login
> or auth layer. `portfolio` holds exactly one row representing your
> virtual account. (If you later want to demo this to other people, add
> a `users` table back and re-attach `user_id` foreign keys.)

## portfolio

``` text
id
virtual_cash
created_at
```

## positions

``` text
id
stock_id
quantity
average_price
```

## trades

``` text
id
stock_id
strategy_id
side
quantity
price
timestamp
reason
```

## strategies

``` text
id
name
description
parameters
created_at
```

## signals

``` text
id
strategy_id
stock_id
timestamp
signal
price
reason
```

## backtests

``` text
id
strategy_id
start_date
end_date
initial_capital
final_capital
return_pct
max_drawdown
trade_count
```

------------------------------------------------------------------------

# 23. API Design

Example endpoints:

``` text
GET    /api/stocks
POST   /api/stocks

GET    /api/stocks/{symbol}/prices

GET    /api/portfolio

GET    /api/positions

POST   /api/orders/buy
POST   /api/orders/sell

GET    /api/trades

GET    /api/strategies
POST   /api/strategies

POST   /api/strategies/{id}/run

POST   /api/backtests

GET    /api/backtests/{id}

GET    /api/signals
```

------------------------------------------------------------------------

# 24. Testing Strategy

Every phase should include tests.

## Unit Tests

Test:

-   Moving average calculations
-   RSI calculations
-   Buy conditions
-   Sell conditions
-   Position sizing
-   P&L calculations
-   Drawdown calculations

## Integration Tests

Test:

``` text
Strategy
   ↓
Signal
   ↓
Order
   ↓
Portfolio
   ↓
P&L
```

## Backtest Validation

Use known small datasets where the expected result can be calculated
manually.

------------------------------------------------------------------------

# 25. Important Algo-Trading Concepts to Teach

The application should eventually cover:

-   Market orders
-   Limit orders
-   Slippage
-   Brokerage
-   Bid/ask spread
-   OHLC
-   Volume
-   Moving averages
-   RSI
-   Bollinger Bands
-   Breakouts
-   Momentum
-   Mean reversion
-   Stop loss
-   Take profit
-   Position sizing
-   Risk/reward
-   Drawdown
-   Backtesting
-   Look-ahead bias
-   Survivorship bias
-   Overfitting
-   Data leakage
-   Walk-forward testing
-   Out-of-sample testing
-   Paper trading

------------------------------------------------------------------------

# 26. Security and Safety Principles

The initial application must remain a simulator.

Do not store real broker credentials in the early phases.

Do not implement live order execution until the learning and
paper-trading layers are thoroughly tested.

If broker connectivity is eventually added:

-   Use environment variables/secrets management.
-   Never hard-code API keys.
-   Separate paper and live environments.
-   Add explicit safeguards around order execution.
-   Log every order request.
-   Add position and loss limits.

## Angel One (SmartAPI) Credentials

Since Angel One is the intended data provider from Phase 11 onward:

-   Store the API key, client code, password/PIN, and TOTP secret in a
    `.env` file (or OS secrets store), loaded via config --- never in
    Git, never in a notebook cell, never printed to logs.
-   Add `.env` to `.gitignore` from Phase 0, before any credential ever
    exists, so it's never accidentally committed later.
-   Treat the Angel One session token as short-lived: refresh it through
    your own auth module rather than hard-coding it anywhere.
-   Even though Angel One's API can place real orders, this project must
    never call those endpoints --- see the Phase 12 note on paper orders.

------------------------------------------------------------------------

# 27. Recommended MVP

Do **not** build all phases at once.

The first usable version should contain only:

### MVP V1

1.  Dummy stocks
2.  Virtual ₹1,00,000 cash
3.  Simulated price history
4.  Price chart
5.  BUY button
6.  SELL button
7.  Positions
8.  Portfolio value
9.  P&L
10. Trade history
11. Reset simulation

Then add:

### MVP V2

12. Moving Average strategy
13. Automatic BUY/SELL signals
14. Strategy parameters
15. Signal explanations

Then:

### MVP V3

16. Backtesting
17. Risk management
18. Performance analytics

This keeps the project manageable and makes every version usable.

------------------------------------------------------------------------

# 28. Definition of Done

The project can be considered a successful learning platform when a user
can:

-   Create a dummy stock.
-   Generate price data.
-   Start with virtual cash.
-   Manually trade.
-   See portfolio P&L.
-   Create a strategy.
-   Generate automated signals.
-   Understand why a signal occurred.
-   Backtest the strategy.
-   Apply risk management.
-   Analyze results.
-   Compare strategies.
-   Run paper trades using market data.
-   Explain the difference between a strategy, signal, order, position,
    portfolio, and backtest.

------------------------------------------------------------------------

# 29. Final Project Goal

The end product should feel like:

> **"A small trading laboratory where I can experiment with algorithms
> and understand what the computer is doing."**

The project should prioritize **learning, transparency, experimentation,
and safe simulation** over live trading.

The most important principle is:

``` text
Understand
    ↓
Experiment
    ↓
Backtest
    ↓
Analyze
    ↓
Paper Trade
    ↓
Only then consider real-world systems
```
