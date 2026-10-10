"""Replay one strategy over several stocks that share a single pool of cash. Pure logic: no DB, no I/O.

Every day follows the same order as the one-stock engine (engine/backtest.py), applied to each stock that has a
price that day: orders decided yesterday fill at today's open, an order-level stop or target is checked, the
Risk-management close-stop is checked, then today's signal is acted on. What is new is what the stocks share:
the cash, the equity every position is sized from, and the Risk limits that look at the whole portfolio
(maximum open positions, maximum share of equity in one stock). Those mirror live trading (risk_service).
"""

from dataclasses import dataclass, field
from datetime import date

from ..strategies.base import StrategyDef
from . import cost_math, exit_math, indicators, risk_math
from .backtest import FILL_MODES, BacktestResult, BacktestTrade, EquityPoint, ExitConfig, RiskConfig, _close_trade
from .cost_math import CostConfig

SKIP_REASONS = ("cash", "allocation", "max_positions", "size")


@dataclass
class StockSeries:
    """One stock's prices, oldest first. Days before `start_index` only warm the indicators up."""

    symbol: str
    dates: list[date]
    closes: list[float]
    opens: list[float] | None = None
    highs: list[float] | None = None
    lows: list[float] | None = None
    start_index: int = 0


@dataclass
class PortfolioResult(BacktestResult):
    """A BacktestResult for the whole account (trades carry their symbol), plus what only a portfolio has."""

    skipped_by_reason: dict = field(default_factory=dict)  # why buys were skipped: cash, allocation, max_positions, size
    unfilled_signals: int = 0  # next-open mode: decisions still waiting when the data ran out
    peak_positions: int = 0  # most stocks held at once
    invested_days: int = 0  # days with at least one position open at the close


def calendar(stocks: list[StockSeries]) -> list[date]:
    """Every day any stock traded in the period, oldest first."""
    days: set[date] = set()
    for s in stocks:
        days.update(s.dates[s.start_index:])
    return sorted(days)


def equal_weight_curve(stocks: list[StockSeries], days: list[date], initial_capital: float) -> list[float]:
    """What the same money would have been worth split equally across the stocks on the first day and never
    touched: a stock not yet trading stays as cash, one with no price today keeps its last close."""
    share = initial_capital / len(stocks)
    units: list[float | None] = [None] * len(stocks)
    index = [{d: i for i, d in enumerate(s.dates)} for s in stocks]
    last: list[float | None] = [None] * len(stocks)
    out: list[float] = []
    for day in days:
        total = 0.0
        for k, s in enumerate(stocks):
            i = index[k].get(day)
            if i is not None and i >= s.start_index:
                last[k] = s.closes[i]
                if units[k] is None:
                    units[k] = share / s.closes[i]
            total += units[k] * last[k] if units[k] is not None else share
        out.append(total)
    return out


def run_portfolio_backtest(
    defn: StrategyDef,
    params: dict,
    stocks: list[StockSeries],
    quantity: int,
    initial_capital: float,
    risk: RiskConfig | None = None,
    costs: CostConfig | None = None,
    fill_mode: str = "signal_close",
    exits: ExitConfig | None = None,
    max_open_positions: int = 0,
) -> PortfolioResult:
    """Trade `defn` on every stock in `stocks` from one account of `initial_capital`.

    Stocks are handled in alphabetical order of symbol, so when two BUYs land on the same day the earlier symbol
    is tried first and, if the cash or a limit then runs out, the later one is skipped (counted in
    `skipped_buys` with its reason in `skipped_by_reason`). Sells are always carried out before buys on a day, so
    money from an exit is available to a buy the same day. Each buy is sized from the account's equity at that
    moment with the same formula live auto-trading uses; a stock with no price on a day is skipped that day and
    kept at its last close.

    `max_open_positions` (0 = no limit) and `risk.max_allocation_pct` only apply while `risk.enabled`, exactly as
    in live trading. `fill_mode`, `exits`, `costs` and `risk` mean what they mean in `run_backtest`; a stock's
    signals come from its own closes and never look ahead.
    """
    if fill_mode not in FILL_MODES:
        raise ValueError(f"Unknown fill mode '{fill_mode}'. Choose one of: {', '.join(FILL_MODES)}")
    if not stocks:
        raise ValueError("Choose at least one stock")
    next_open = fill_mode == "next_open"
    exits = exits if exits is not None else ExitConfig()
    risk = risk if risk is not None else RiskConfig()
    costs = costs if costs is not None else CostConfig()
    stocks = sorted(stocks, key=lambda s: s.symbol)
    for s in stocks:
        n = len(s.closes)
        if next_open and (s.opens is None or len(s.opens) != n):
            raise ValueError(f"{s.symbol}: next-open fills need one opening price per close")
        if exits.enabled and any(series is None or len(series) != n for series in (s.opens, s.highs, s.lows)):
            raise ValueError(f"{s.symbol}: order-level stops need one open, high and low per close")

    events = [{e.index: e for e in defn.generate(s.closes, params)} for s in stocks]
    volatility = [
        indicators.volatility_pct(s.closes, risk.volatility_window)
        if risk.enabled and risk.stop_mode == "volatility" and risk.volatility_window >= 2
        else None
        for s in stocks
    ]
    row_of = [{d: i for i, d in enumerate(s.dates)} for s in stocks]
    days = calendar(stocks)

    cash = initial_capital
    held = [0] * len(stocks)
    open_trade: list[BacktestTrade | None] = [None] * len(stocks)
    last_close: list[float | None] = [None] * len(stocks)
    pending: list[tuple | None] = [None] * len(stocks)
    trades: list[BacktestTrade] = []
    equity_curve: list[EquityPoint] = []
    skipped = {reason: 0 for reason in SKIP_REASONS}
    stopped_out = take_profits = invested_days = peak_positions = 0
    total_fees = slippage_cost = 0.0
    peak = initial_capital
    max_drawdown_pct = 0.0

    def portfolio_equity() -> float:
        return cash + sum(held[k] * last_close[k] for k in range(len(stocks)) if held[k])

    def sell(k: int, day: date, quote: float, *, stopped: bool = False, reason: str | None = None) -> None:
        nonlocal cash, total_fees, slippage_cost, stopped_out
        fill = cost_math.fill_price(quote, "SELL", costs)
        proceeds = fill * held[k]
        fees = cost_math.charges(proceeds, costs)
        cash += proceeds - fees
        total_fees += fees
        slippage_cost += (quote - fill) * held[k]
        _close_trade(open_trade[k], day, fill, stopped_out=stopped, exit_fees=fees, reason=reason or ("risk_stop" if stopped else "signal"))
        held[k] = 0
        open_trade[k] = None
        if stopped:
            stopped_out += 1

    def buy(k: int, day: date, quote: float, equity: float, buy_qty: int, stop_pct: float | None) -> None:
        nonlocal cash, total_fees, slippage_cost, peak_positions
        fill = cost_math.fill_price(quote, "BUY", costs)
        cost = fill * buy_qty
        fees = cost_math.charges(cost, costs)
        reason = None
        if buy_qty <= 0:
            reason = "size"
        elif risk.enabled and max_open_positions and sum(1 for h in held if h) >= max_open_positions:
            reason = "max_positions"
        elif cost + fees > cash:
            reason = "cash"
        elif risk.enabled and risk.max_allocation_pct and equity > 0 and quote * buy_qty > equity * risk.max_allocation_pct / 100 + 1e-9:
            reason = "allocation"
        if reason:
            skipped[reason] += 1
            return
        cash -= cost + fees
        held[k] = buy_qty
        total_fees += fees
        slippage_cost += (fill - quote) * buy_qty
        trade = BacktestTrade(entry_date=day, entry_price=fill, quantity=buy_qty, stop_pct=stop_pct, entry_fees=fees, symbol=stocks[k].symbol)
        open_trade[k] = trade
        trades.append(trade)
        peak_positions = max(peak_positions, sum(1 for h in held if h))

    for day in days:
        # Today's row in each stock that has a price (and has begun trading); `today[k]` is None for the others.
        today = [row_of[k].get(day) for k in range(len(stocks))]
        today = [i if i is not None and i >= stocks[k].start_index else None for k, i in enumerate(today)]
        todays_event = [events[k].get(i) if i is not None else None for k, i in enumerate(today)]
        for k, i in enumerate(today):
            if i is not None:
                last_close[k] = stocks[k].closes[i]

        # 1. Orders decided at a previous close fill at today's open: sells first, so their cash can fund the buys.
        for side in ("SELL", "BUY"):
            for k, i in enumerate(today):
                if i is not None and pending[k] is not None and pending[k][0] == side:
                    if side == "BUY":
                        # Allocation is judged against the equity as of the last close, as the one-stock engine does.
                        equity = cash + sum(held[j] * last_close[j] for j in range(len(stocks)) if held[j] and j != k)
                        buy(k, day, stocks[k].opens[i], equity, pending[k][1], pending[k][2])
                    else:
                        sell(k, day, stocks[k].opens[i], stopped=pending[k][1])
                    pending[k] = None

        # 2. Order-level stop-loss / take-profit, 3. the Risk-management close-stop.
        for k, i in enumerate(today):
            if i is None:
                continue
            s = stocks[k]
            if exits.enabled and held[k] > 0:
                stop_level, target_level = exits.levels(open_trade[k].entry_price)
                hit = exit_math.exit_fill(s.opens[i], s.highs[i], s.lows[i], stop_level, target_level)
                if hit is not None:
                    sell(k, day, hit.price, stopped=hit.kind == "stop", reason="stop_loss" if hit.kind == "stop" else "take_profit")
                    if hit.kind == "target":
                        take_profits += 1
            open_stop_pct = (open_trade[k].stop_pct or risk.stop_loss_pct) if held[k] > 0 else None
            if risk.enabled and open_stop_pct and held[k] > 0 and pending[k] is None:
                if s.closes[i] <= risk_math.stop_loss_price(open_trade[k].entry_price, open_stop_pct):
                    if next_open:
                        pending[k] = ("SELL", True)
                    else:
                        sell(k, day, s.closes[i], stopped=True)
                    todays_event[k] = None  # the strategy's own signal is superseded for today

        # 4. Today's signals: sells first, then buys in symbol order.
        for k, i in enumerate(today):
            ev = todays_event[k]
            if i is not None and ev is not None and ev.side == "SELL" and held[k] > 0 and pending[k] is None:
                if next_open:
                    pending[k] = ("SELL", False)
                else:
                    sell(k, day, stocks[k].closes[i])
        for k, i in enumerate(today):
            ev = todays_event[k]
            if i is None or ev is None or ev.side != "BUY" or held[k] > 0 or pending[k] is not None:
                continue
            price = stocks[k].closes[i]
            equity = portfolio_equity()
            stop_pct = None
            if risk.enabled:
                stop_pct = (
                    risk_math.volatility_stop_pct(volatility[k][i], risk.volatility_multiplier, risk.stop_loss_pct)
                    if volatility[k] is not None
                    else risk.stop_loss_pct
                )
            buy_qty = (
                risk_math.position_size(equity, price, risk.max_risk_per_trade_pct, stop_pct, quantity, risk.max_allocation_pct)
                if risk.enabled
                else quantity
            )
            if not next_open:
                buy(k, day, price, equity, buy_qty, stop_pct)
            elif buy_qty > 0:
                pending[k] = ("BUY", buy_qty, stop_pct)
            else:
                skipped["size"] += 1

        equity = portfolio_equity()
        equity_curve.append(EquityPoint(date=day, value=equity))
        if any(held):
            invested_days += 1
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown_pct = max(max_drawdown_pct, (peak - equity) / peak * 100)

    final_capital = equity_curve[-1].value if equity_curve else initial_capital
    closed = [t for t in trades if not t.is_open]
    winning = sum(1 for t in closed if t.pnl > 0)
    return PortfolioResult(
        initial_capital=initial_capital,
        final_capital=final_capital,
        total_return_pct=(final_capital - initial_capital) / initial_capital * 100 if initial_capital else 0.0,
        total_trades=len(closed),
        winning_trades=winning,
        losing_trades=len(closed) - winning,
        win_rate_pct=(winning / len(closed) * 100) if closed else 0.0,
        max_drawdown_pct=max_drawdown_pct,
        skipped_buys=sum(skipped.values()),
        stopped_out=stopped_out,
        take_profits=take_profits,
        stop_loss_pct=exits.stop_pct or None,
        take_profit_pct=exits.target_pct or None,
        costs_applied=costs.enabled,
        total_fees=total_fees,
        slippage_cost=slippage_cost,
        fill_mode=fill_mode,
        unfilled_signal=any(p is not None for p in pending),
        equity_curve=equity_curve,
        trades=trades,
        skipped_by_reason=skipped,
        unfilled_signals=sum(1 for p in pending if p is not None),
        peak_positions=peak_positions,
        invested_days=invested_days,
    )
