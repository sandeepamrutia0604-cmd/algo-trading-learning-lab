"""Performance metrics for a backtest. Pure logic: no database, no I/O.

A backtest reports a total return and a max drawdown, which say how much was made and the worst
fall. They don't say how *smooth* the ride was, how much was made for each unit of risk taken,
what the typical trade looked like, how long the strategy was actually invested, or whether it did
any better than simply holding the stock or an index. These functions answer those, from the
account's daily value curve and the list of closed trades.

Conventions, chosen to match the Performance page (services/analytics_service.py):
  - 252 trading days make a year.
  - Volatility and Sharpe use the population standard deviation of daily returns.
  - The risk-free rate is a yearly percentage (0 by default), spread evenly over the 252 days.
  - Daily returns come from the account value on each traded day, so days spent in cash count as
    zero-return days, as they should: they are part of the strategy's record.
"""

import math
import statistics

TRADING_DAYS_PER_YEAR = 252
MIN_OVERLAP_DAYS = 20  # fewer shared days than this and a beta says nothing


def daily_returns(values: list[float]) -> list[float]:
    """Day-over-day change of a value series, as fractions (0.01 is +1%)."""
    return [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1] > 0]


def _daily_risk_free(risk_free_pct: float) -> float:
    return risk_free_pct / 100 / TRADING_DAYS_PER_YEAR


def cagr_pct(initial: float, final: float, days: int) -> float | None:
    """Compound annual growth rate over `days` daily steps. None when there is no time span."""
    if days <= 0 or initial <= 0:
        return None
    if final <= 0:
        return -100.0
    return ((final / initial) ** (TRADING_DAYS_PER_YEAR / days) - 1) * 100


def annualised_volatility_pct(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    return statistics.pstdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100


def sharpe_ratio(returns: list[float], risk_free_pct: float = 0.0) -> float | None:
    """Average return above the risk-free rate per unit of volatility, annualised. None when the
    returns never vary (nothing to divide by)."""
    if len(returns) < 2:
        return None
    spread = statistics.pstdev(returns)
    if spread <= 0:
        return None
    return (statistics.mean(returns) - _daily_risk_free(risk_free_pct)) / spread * math.sqrt(TRADING_DAYS_PER_YEAR)


def sortino_ratio(returns: list[float], risk_free_pct: float = 0.0) -> float | None:
    """Like Sharpe, but only falling days count as risk: the downside deviation is the root mean
    square of the shortfall below the risk-free rate, over all days. None when there was no
    downside at all."""
    if len(returns) < 2:
        return None
    target = _daily_risk_free(risk_free_pct)
    downside = math.sqrt(sum(min(r - target, 0.0) ** 2 for r in returns) / len(returns))
    if downside <= 0:
        return None
    return (statistics.mean(returns) - target) / downside * math.sqrt(TRADING_DAYS_PER_YEAR)


def calmar_ratio(cagr: float | None, max_drawdown_pct: float) -> float | None:
    """Annual growth per unit of worst fall. None when there was no drawdown or no growth rate."""
    if cagr is None or max_drawdown_pct <= 0:
        return None
    return cagr / max_drawdown_pct


def longest_drawdown_days(values: list[float]) -> int:
    """The longest stretch, in trading days, spent below a previous peak: the time it took (or, at
    the end of the series, is taking) to get back to a new high."""
    peak, longest, current = float("-inf"), 0, 0
    for value in values:
        if value >= peak:
            peak, current = value, 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def beta_alpha(strategy: list[float], benchmark: list[float], risk_free_pct: float = 0.0) -> dict | None:
    """How the strategy's daily returns relate to a benchmark's (the two lists must line up day by
    day). beta: how many percent the strategy has tended to move for each 1% the benchmark moved.
    alpha: the yearly return the strategy made beyond what that beta alone would explain (Jensen's
    alpha, in percent). correlation: how closely the two moved together, -1 to 1."""
    if len(strategy) != len(benchmark) or len(strategy) < MIN_OVERLAP_DAYS:
        return None
    variance = statistics.pvariance(benchmark)
    if variance <= 0:
        return None
    mean_s, mean_b = statistics.mean(strategy), statistics.mean(benchmark)
    covariance = sum((s - mean_s) * (b - mean_b) for s, b in zip(strategy, benchmark)) / len(strategy)
    beta = covariance / variance
    spread_s = statistics.pstdev(strategy)
    rf = _daily_risk_free(risk_free_pct)
    return {
        "beta": beta,
        "alpha_pct": ((mean_s - rf) - beta * (mean_b - rf)) * TRADING_DAYS_PER_YEAR * 100,
        "correlation": covariance / (math.sqrt(variance) * spread_s) if spread_s > 0 else None,
    }


def aligned_returns(first: list[float], second: list[float]) -> tuple[list[float], list[float]]:
    """Day-over-day returns of two equally long value series, keeping only the days both can compute
    (a zero or negative value on the previous day has no return), so the two lists stay in step."""
    a, b = [], []
    for i in range(1, min(len(first), len(second))):
        if first[i - 1] > 0 and second[i - 1] > 0:
            a.append(first[i] / first[i - 1] - 1)
            b.append(second[i] / second[i - 1] - 1)
    return a, b


def trade_stats(pnls: list[float], holding_days: list[int]) -> dict:
    """What the closed trades looked like. `pnls` are rupee profits and losses after costs;
    `holding_days` the number of trading days each was held."""
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_profit, gross_loss = sum(wins), -sum(losses)
    average_win = gross_profit / len(wins) if wins else None
    average_loss = -gross_loss / len(losses) if losses else None
    streak = longest = 0
    for p in pnls:
        streak = streak + 1 if p <= 0 else 0
        longest = max(longest, streak)
    return {
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
        "average_win": average_win,
        "average_loss": average_loss,
        "payoff_ratio": average_win / -average_loss if average_win is not None and average_loss else None,
        "expectancy": sum(pnls) / len(pnls) if pnls else None,
        "best_trade": max(pnls) if pnls else None,
        "worst_trade": min(pnls) if pnls else None,
        "max_consecutive_losses": longest,
        "average_holding_days": sum(holding_days) / len(holding_days) if holding_days else None,
    }
