import math
import statistics
from datetime import date

from sqlalchemy.orm import Session

from ..models import Trade
from ..models.portfolio import INITIAL_VIRTUAL_CASH

TRADING_DAYS_PER_YEAR = 252


def trade_stats(trades: list[Trade]) -> dict:
    """Win rate, average win/loss and profit factor over a set of closed (SELL) trades."""
    closed = [t for t in trades if t.realized_pnl is not None]
    wins = [t.realized_pnl for t in closed if t.realized_pnl > 0]
    losses = [t.realized_pnl for t in closed if t.realized_pnl <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "total_trades": len(closed),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": (len(wins) / len(closed) * 100) if closed else 0.0,
        "avg_win": (gross_profit / len(wins)) if wins else 0.0,
        "avg_loss": (-gross_loss / len(losses)) if losses else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
    }


def equity_metrics(curve: list[dict]) -> dict:
    """Max drawdown % and an annualized Sharpe ratio (0% risk-free rate) from a value curve."""
    if len(curve) < 2:
        return {"max_drawdown_pct": 0.0, "sharpe_ratio": None}

    values = [c["value"] for c in curve]
    peak = values[0]
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak * 100)

    daily_returns = [
        (values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values)) if values[i - 1] > 0
    ]
    sharpe = None
    if len(daily_returns) >= 2:
        stdev = statistics.pstdev(daily_returns)
        if stdev > 0:
            sharpe = (statistics.mean(daily_returns) / stdev) * math.sqrt(TRADING_DAYS_PER_YEAR)

    return {"max_drawdown_pct": max_dd, "sharpe_ratio": sharpe}


def drawdown_curve(curve: list[dict]) -> list[dict]:
    """Percent decline from the running peak, per point — for a drawdown chart."""
    result = []
    peak = None
    for c in curve:
        peak = c["value"] if peak is None else max(peak, c["value"])
        pct = ((c["value"] - peak) / peak * 100) if peak else 0.0
        result.append({"date": c["date"], "value": pct})
    return result


def monthly_returns(curve: list[dict]) -> list[dict]:
    """% change in portfolio value for each calendar month that has data."""
    if not curve:
        return []
    by_month: dict[str, float] = {}
    for point in curve:
        by_month[point["date"].strftime("%Y-%m")] = point["value"]  # last value of the month wins

    result = []
    prev_end = INITIAL_VIRTUAL_CASH
    for month in sorted(by_month):
        end = by_month[month]
        pct = ((end - prev_end) / prev_end * 100) if prev_end else 0.0
        result.append({"month": month, "return_pct": pct})
        prev_end = end
    return result


def strategy_comparison(db: Session) -> list[dict]:
    """Trade-level performance grouped by the strategy that placed each closed trade
    (manual trades are grouped as "Manual"), sorted by total realized P&L."""
    trades = db.query(Trade).filter(Trade.realized_pnl.isnot(None)).all()
    groups: dict[int | None, list[Trade]] = {}
    for t in trades:
        groups.setdefault(t.strategy_id, []).append(t)

    rows = []
    for strategy_id, group in groups.items():
        stats = trade_stats(group)
        name = group[0].strategy.name if strategy_id else "Manual"
        rows.append({"strategy_id": strategy_id, "name": name, "total_pnl": sum(t.realized_pnl for t in group), **stats})
    rows.sort(key=lambda r: r["total_pnl"], reverse=True)
    return rows
