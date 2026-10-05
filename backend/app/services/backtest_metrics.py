"""The extra numbers shown under a backtest: risk-adjusted returns, what the trades looked like, how
long the strategy was invested, and how it compares with buy-and-hold and an optional benchmark
(see engine/metrics.py for the maths and its conventions)."""

from datetime import date

from sqlalchemy.orm import Session

from ..adapters import get_market_data_adapter
from ..engine import metrics
from ..engine.backtest import BacktestResult


def _benchmark(db: Session, symbol: str, dates: list[date], values: list[float], risk_free_pct: float) -> dict:
    """How the strategy did against another stock or index over the days both have prices for."""
    closes_by_date = {c.date: c.close for c in get_market_data_adapter(db, full_history=True).get_historical_candles(symbol)}
    common = [(d, v) for d, v in zip(dates, values) if d in closes_by_date]
    out = {
        "symbol": symbol.upper(),
        "days": len(common),
        "return_pct": None,
        "strategy_return_pct": None,
        "excess_return_pct": None,
        "beta": None,
        "alpha_pct": None,
        "correlation": None,
    }
    if len(common) < 2:
        return out
    strategy_values = [v for _, v in common]
    benchmark_values = [closes_by_date[d] for d, _ in common]
    out["return_pct"] = (benchmark_values[-1] / benchmark_values[0] - 1) * 100
    out["strategy_return_pct"] = (strategy_values[-1] / strategy_values[0] - 1) * 100  # over the same stretch
    out["excess_return_pct"] = out["strategy_return_pct"] - out["return_pct"]
    strategy_returns, benchmark_returns = metrics.aligned_returns(strategy_values, benchmark_values)
    out.update(metrics.beta_alpha(strategy_returns, benchmark_returns, risk_free_pct) or {})
    return out


def compute(
    db: Session,
    result: BacktestResult,
    dates: list[date],
    closes: list[float],
    risk_free_pct: float = 0.0,
    benchmark: str | None = None,
) -> dict:
    """`dates` and `closes` are the series the backtest ran on (including any warm-up days before
    the traded period), `result` its output."""
    curve = result.equity_curve
    curve_dates = [p.date for p in curve]
    values = [p.value for p in curve]
    days = len(values) - 1
    returns = metrics.daily_returns(values)

    cagr = metrics.cagr_pct(result.initial_capital, result.final_capital, days)
    position_of = {d: i for i, d in enumerate(dates)}
    last = position_of[curve_dates[-1]]
    closed = [t for t in result.trades if not t.is_open]
    # A position counts as held on each close from the day it was opened up to the day before it was sold.
    held_days = sum((position_of[t.exit_date] if t.exit_date else last + 1) - position_of[t.entry_date] for t in result.trades)

    start = position_of[curve_dates[0]]
    held_return = (closes[last] / closes[start] - 1) * 100
    held_cagr = metrics.cagr_pct(1.0, 1 + held_return / 100, days)

    return {
        "risk_free_pct": risk_free_pct,
        "trading_days": len(values),
        "years": len(values) / metrics.TRADING_DAYS_PER_YEAR,
        "cagr_pct": cagr,
        "volatility_pct": metrics.annualised_volatility_pct(returns),
        "sharpe": metrics.sharpe_ratio(returns, risk_free_pct),
        "sortino": metrics.sortino_ratio(returns, risk_free_pct),
        "calmar": metrics.calmar_ratio(cagr, result.max_drawdown_pct),
        "longest_drawdown_days": metrics.longest_drawdown_days(values),
        "days_in_market": held_days,
        "exposure_pct": held_days / len(values) * 100,
        "trade_stats": metrics.trade_stats(
            [t.pnl for t in closed], [position_of[t.exit_date] - position_of[t.entry_date] for t in closed]
        ),
        "buy_hold": {
            "return_pct": held_return,
            "cagr_pct": held_cagr,
            "excess_return_pct": result.total_return_pct - held_return,
        },
        "benchmark": _benchmark(db, benchmark, curve_dates, values, risk_free_pct) if benchmark else None,
    }
