"""Replay a strategy's signals over price history with real cash. Pure logic: no DB, no I/O."""

from dataclasses import dataclass, field
from datetime import date

from ..strategies.base import StrategyDef
from . import cost_math, exit_math, indicators, risk_math
from .cost_math import CostConfig


@dataclass
class RiskConfig:
    """The subset of RiskSettings that applies to a single-stock backtest.

    max_open_positions is deliberately not here: a backtest only ever trades one stock, so
    a strategy that is long-only (at most one open position at a time, enforced upstream by
    long_only_signals) already satisfies any max-open-positions setting >= 1 by construction.
    """

    enabled: bool = False
    max_risk_per_trade_pct: float = 0.0
    stop_loss_pct: float = 0.0
    max_allocation_pct: float = 0.0
    stop_mode: str = "fixed"  # or "volatility": see risk_math.entry_stop_pct
    volatility_window: int = 20
    volatility_multiplier: float = 2.0


@dataclass(frozen=True)
class ExitConfig:
    """An order-level stop-loss and take-profit, as percentages of each trade's entry price: the same two
    levels a live paper order can carry (engine/exit_math.py). Checked every day against that day's open,
    high and low, and independent of the Risk management stop (which looks at closes and sizes the position)."""

    stop_pct: float | None = None
    target_pct: float | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.stop_pct or self.target_pct)

    def levels(self, entry_price: float) -> tuple[float | None, float | None]:
        """(stop price, target price) for a trade that entered at `entry_price`, rounded to 2 decimals like
        the order ticket does (unless rounding would put a level on the wrong side of the entry)."""
        stop = target = None
        if self.stop_pct:
            raw = entry_price * (1 - self.stop_pct / 100)
            stop = round(raw, 2) if round(raw, 2) < entry_price else raw
        if self.target_pct:
            raw = entry_price * (1 + self.target_pct / 100)
            target = round(raw, 2) if round(raw, 2) > entry_price else raw
        return stop, target


@dataclass
class BacktestTrade:
    entry_date: date
    entry_price: float
    quantity: int
    exit_date: date | None = None
    exit_price: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    stopped_out: bool = False  # closed by a stop-loss of either kind (Risk management or order-level)
    exit_reason: str | None = None  # "signal", "risk_stop", "stop_loss" or "take_profit"; None while open
    stop_pct: float | None = None  # the stop distance this trade was sized and protected with
    entry_fees: float = 0.0
    exit_fees: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_date is None


@dataclass
class EquityPoint:
    date: date
    value: float


@dataclass
class BacktestResult:
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    max_drawdown_pct: float
    skipped_buys: int
    stopped_out: int = 0
    take_profits: int = 0  # trades closed by an order-level take-profit
    stop_loss_pct: float | None = None  # the order-level levels this run used, if any
    take_profit_pct: float | None = None
    costs_applied: bool = False
    total_fees: float = 0.0
    slippage_cost: float = 0.0
    fill_mode: str = "signal_close"
    unfilled_signal: bool = False  # next-open mode: a decision on the final day had no next day to trade on
    equity_curve: list[EquityPoint] = field(default_factory=list)
    trades: list[BacktestTrade] = field(default_factory=list)


# When a decision is carried out. "signal_close": at the close of the day the signal appears (the
# signal is computed from that close, so this assumes you could trade at a price you only learn once
# the day is over: optimistic). "next_open": at the opening price of the next trading day, the first
# price you could really have got.
FILL_MODES = ("signal_close", "next_open")


def _close_trade(
    trade: BacktestTrade,
    day: date,
    price: float,
    *,
    stopped_out: bool = False,
    exit_fees: float = 0.0,
    reason: str = "signal",
) -> None:
    trade.exit_reason = reason
    trade.exit_date = day
    trade.exit_price = price
    trade.exit_fees = exit_fees
    trade.pnl = (price - trade.entry_price) * trade.quantity - trade.entry_fees - exit_fees
    if trade.entry_fees or exit_fees:
        trade.pnl_pct = trade.pnl / (trade.entry_price * trade.quantity + trade.entry_fees) * 100
    else:
        trade.pnl_pct = (price - trade.entry_price) / trade.entry_price * 100
    trade.stopped_out = stopped_out


def run_backtest(
    defn: StrategyDef,
    params: dict,
    dates: list[date],
    closes: list[float],
    quantity: int,
    initial_capital: float,
    risk: RiskConfig | None = None,
    costs: CostConfig | None = None,
    start_index: int = 0,
    fill_mode: str = "signal_close",
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    exits: ExitConfig | None = None,
) -> BacktestResult:
    """Process `dates`/`closes` chronologically, buying/selling on each signal at that day's
    close, marking to market every day. A BUY is skipped if it would cost more than the cash
    on hand, or breach `risk.max_allocation_pct` (recorded in `skipped_buys`) rather than
    going short; the engine's long/flat state still tracks the strategy's own alternating
    assumption, since a SELL only fires once a BUY actually filled.

    When `risk` is enabled, each BUY is sized from `risk.max_risk_per_trade_pct` and
    `risk.stop_loss_pct` instead of the fixed `quantity` (same formula as live auto-trading),
    shrunk to fit `risk.max_allocation_pct` rather than skipped for exceeding it, and a held position is stop-lossed out the first day its close drops to or below the
    entry's stop price — overriding the strategy's own signal for that day, exactly like
    live auto-trading's own stop-loss check.

    `defn.generate()` (from the strategy registry) only ever looks at closes up to the
    signal's own day, so this carries over the no-look-ahead guarantee already enforced there.

    `start_index` begins trading part-way through the series: the days before it are only used
    to warm the indicators up (they are past data, so nothing is peeked at), and no trade,
    capital or equity point exists for them. The account starts with `initial_capital` on day
    `start_index`.

    `fill_mode` "next_open" (needs `opens`, one per close) carries out everything decided at a
    day's close, a signal or a stop-loss, at the next trading day's opening price instead. The
    size of a BUY is still worked out at the decision, from the signal day's close (all that is
    known then); whether the cash and allocation cap allow it is checked at the open it fills at. A
    decision on the final day has no next day and is dropped (`unfilled_signal`). The account is
    still marked to market at each close.

    `exits` adds an order-level stop-loss and/or take-profit (needs `opens`, `highs` and `lows`, one per
    close). Each day, before anything else is decided, an open trade is checked against that day's candle
    with the same rule live orders use (engine/exit_math.py): a gap beyond a level fills at the open,
    otherwise the level itself, and a day that reaches both takes the stop. A trade that entered at a close
    is first checked the next day; one that entered at an open is live from that day. The exit is sold
    through the ordinary sell path (slippage and charges apply). It does not size the position.
    """
    if fill_mode not in FILL_MODES:
        raise ValueError(f"Unknown fill mode '{fill_mode}'. Choose one of: {', '.join(FILL_MODES)}")
    next_open = fill_mode == "next_open"
    if next_open and (opens is None or len(opens) != len(closes)):
        raise ValueError("Next-open fills need one opening price per close")
    exits = exits if exits is not None else ExitConfig()
    if exits.enabled and any(series is None or len(series) != len(closes) for series in (opens, highs, lows)):
        raise ValueError("Order-level stops need one open, high and low per close")
    events_by_index = {e.index: e for e in defn.generate(closes, params)}
    risk = risk if risk is not None else RiskConfig()
    costs = costs if costs is not None else CostConfig()

    # Daily volatility as of each day (None until there is enough history). Each value only looks
    # at that day and the days before it, so reading it at a BUY's day peeks at nothing.
    volatility = (
        indicators.volatility_pct(closes, risk.volatility_window)
        if risk.enabled and risk.stop_mode == "volatility" and risk.volatility_window >= 2
        else None
    )

    cash = initial_capital
    held = 0
    trades: list[BacktestTrade] = []
    equity_curve: list[EquityPoint] = []
    skipped_buys = 0
    stopped_out = 0
    take_profits = 0
    total_fees = 0.0
    slippage_cost = 0.0
    peak = initial_capital
    max_drawdown_pct = 0.0

    def execute_sell(day: date, quote: float, *, stopped: bool = False, reason: str | None = None) -> None:
        nonlocal cash, held, total_fees, slippage_cost, stopped_out
        fill = cost_math.fill_price(quote, "SELL", costs)
        proceeds = fill * held
        fees = cost_math.charges(proceeds, costs)
        cash += proceeds - fees
        total_fees += fees
        slippage_cost += (quote - fill) * held
        _close_trade(trades[-1], day, fill, stopped_out=stopped, exit_fees=fees, reason=reason or ("risk_stop" if stopped else "signal"))
        held = 0
        if stopped:
            stopped_out += 1

    def execute_buy(day: date, quote: float, equity: float, buy_qty: int, stop_pct: float | None) -> None:
        nonlocal cash, held, total_fees, slippage_cost, skipped_buys
        fill = cost_math.fill_price(quote, "BUY", costs)
        cost = fill * buy_qty
        fees = cost_math.charges(cost, costs)
        allowed = buy_qty > 0 and cost + fees <= cash
        if allowed and risk.enabled and risk.max_allocation_pct and equity > 0 and quote * buy_qty > equity * risk.max_allocation_pct / 100 + 1e-9:
            allowed = False
        if allowed:
            cash -= cost + fees
            held = buy_qty
            total_fees += fees
            slippage_cost += (fill - quote) * buy_qty
            trades.append(BacktestTrade(entry_date=day, entry_price=fill, quantity=buy_qty, stop_pct=stop_pct, entry_fees=fees))
        else:
            skipped_buys += 1

    # next-open mode only: what was decided at yesterday's close and is carried out at today's open,
    # ("BUY", planned quantity, stop %) or ("SELL", stopped by the stop-loss?)
    pending: tuple | None = None

    for i, day in enumerate(dates):
        if i < start_index:
            continue
        price = closes[i]
        event = events_by_index.get(i)

        if pending is not None:
            if pending[0] == "BUY":
                execute_buy(day, opens[i], cash, pending[1], pending[2])
            else:
                execute_sell(day, opens[i], stopped=pending[1])
            pending = None

        if exits.enabled and held > 0:
            stop_level, target_level = exits.levels(trades[-1].entry_price)
            hit = exit_math.exit_fill(opens[i], highs[i], lows[i], stop_level, target_level)
            if hit is not None:
                execute_sell(day, hit.price, stopped=hit.kind == "stop", reason="stop_loss" if hit.kind == "stop" else "take_profit")
                if hit.kind == "target":
                    take_profits += 1

        open_stop_pct = (trades[-1].stop_pct or risk.stop_loss_pct) if held > 0 else None
        if risk.enabled and open_stop_pct and held > 0 and pending is None:
            stop_price = risk_math.stop_loss_price(trades[-1].entry_price, open_stop_pct)
            if price <= stop_price:
                if next_open:
                    pending = ("SELL", True)
                else:
                    execute_sell(day, price, stopped=True)
                event = None  # the strategy's own signal (if any) is superseded for today

        if event is not None and event.side == "BUY" and held == 0 and pending is None:
            equity = cash + held * price
            stop_pct = None
            if risk.enabled:
                stop_pct = (
                    risk_math.volatility_stop_pct(volatility[i], risk.volatility_multiplier, risk.stop_loss_pct)
                    if volatility is not None
                    else risk.stop_loss_pct
                )
            buy_qty = (
                risk_math.position_size(
                    equity, price, risk.max_risk_per_trade_pct, stop_pct, quantity, risk.max_allocation_pct
                )
                if risk.enabled
                else quantity
            )
            if not next_open:
                execute_buy(day, price, equity, buy_qty, stop_pct)
            elif buy_qty > 0:
                pending = ("BUY", buy_qty, stop_pct)
            else:
                skipped_buys += 1
        elif event is not None and event.side == "SELL" and held > 0 and pending is None:
            if next_open:
                pending = ("SELL", False)
            else:
                execute_sell(day, price)

        equity = cash + held * price
        equity_curve.append(EquityPoint(date=day, value=equity))
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown_pct = max(max_drawdown_pct, (peak - equity) / peak * 100)

    final_capital = equity_curve[-1].value if equity_curve else initial_capital
    closed = [t for t in trades if not t.is_open]
    winning = sum(1 for t in closed if t.pnl > 0)
    losing = len(closed) - winning

    return BacktestResult(
        initial_capital=initial_capital,
        final_capital=final_capital,
        total_return_pct=(final_capital - initial_capital) / initial_capital * 100 if initial_capital else 0.0,
        total_trades=len(closed),
        winning_trades=winning,
        losing_trades=losing,
        win_rate_pct=(winning / len(closed) * 100) if closed else 0.0,
        max_drawdown_pct=max_drawdown_pct,
        skipped_buys=skipped_buys,
        stopped_out=stopped_out,
        take_profits=take_profits,
        stop_loss_pct=exits.stop_pct or None,
        take_profit_pct=exits.target_pct or None,
        costs_applied=costs.enabled,
        total_fees=total_fees,
        slippage_cost=slippage_cost,
        fill_mode=fill_mode,
        unfilled_signal=pending is not None,
        equity_curve=equity_curve,
        trades=trades,
    )
