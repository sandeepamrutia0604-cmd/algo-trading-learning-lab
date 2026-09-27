"""Replay a strategy's signals over price history with real cash. Pure logic: no DB, no I/O."""

from dataclasses import dataclass, field
from datetime import date

from ..strategies.base import StrategyDef


@dataclass
class BacktestTrade:
    entry_date: date
    entry_price: float
    quantity: int
    exit_date: date | None = None
    exit_price: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None

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
    equity_curve: list[EquityPoint] = field(default_factory=list)
    trades: list[BacktestTrade] = field(default_factory=list)


def run_backtest(
    defn: StrategyDef,
    params: dict,
    dates: list[date],
    closes: list[float],
    quantity: int,
    initial_capital: float,
) -> BacktestResult:
    """Process `dates`/`closes` chronologically, buying/selling `quantity` shares on each
    signal at that day's close, marking to market every day. A BUY is skipped if it would
    cost more than the cash on hand (recorded in `skipped_buys`) rather than going short;
    the engine's long/flat state still tracks the strategy's own alternating assumption,
    since a SELL only fires once a BUY actually filled.

    `defn.generate()` (from the strategy registry) only ever looks at closes up to the
    signal's own day, so this carries over the no-look-ahead guarantee already enforced there.
    """
    events_by_index = {e.index: e for e in defn.generate(closes, params)}

    cash = initial_capital
    held = 0
    trades: list[BacktestTrade] = []
    equity_curve: list[EquityPoint] = []
    skipped_buys = 0
    peak = initial_capital
    max_drawdown_pct = 0.0

    for i, day in enumerate(dates):
        price = closes[i]
        event = events_by_index.get(i)
        if event is not None and event.side == "BUY" and held == 0:
            cost = price * quantity
            if cost <= cash:
                cash -= cost
                held = quantity
                trades.append(BacktestTrade(entry_date=day, entry_price=price, quantity=quantity))
            else:
                skipped_buys += 1
        elif event is not None and event.side == "SELL" and held > 0:
            open_trade = trades[-1]
            cash += price * held
            open_trade.exit_date = day
            open_trade.exit_price = price
            open_trade.pnl = (price - open_trade.entry_price) * held
            open_trade.pnl_pct = (price - open_trade.entry_price) / open_trade.entry_price * 100
            held = 0

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
        equity_curve=equity_curve,
        trades=trades,
    )
