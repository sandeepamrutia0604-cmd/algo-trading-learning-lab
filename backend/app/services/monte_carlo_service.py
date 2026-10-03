"""Monte Carlo analysis of one backtest: run it, take its closed trades, and re-play them many
times in other orders (or resampled) to show how much of the result was luck. The maths is in
engine/monte_carlo.py; this only turns a backtest request into trade returns and back."""

from sqlalchemy.orm import Session

from ..engine import monte_carlo
from ..schemas import BacktestRequest
from . import backtest_service
from .exceptions import InvalidStrategyError

MIN_TRADES = 5  # fewer closed trades than this and the shuffles say nothing
MIN_SIMULATIONS, MAX_SIMULATIONS = 100, 5000


def analyse(db: Session, request: BacktestRequest, simulations: int, method: str, seed: int | None = None) -> dict:
    if not MIN_SIMULATIONS <= simulations <= MAX_SIMULATIONS:
        raise InvalidStrategyError(f"Use between {MIN_SIMULATIONS} and {MAX_SIMULATIONS} simulations")
    if method not in monte_carlo.METHODS:
        raise InvalidStrategyError(f"Unknown method '{method}'. Choose one of: {', '.join(monte_carlo.METHODS)}")

    defn, _params, _dates, _closes, result, risk_enabled = backtest_service.run(
        db,
        request.symbol,
        request.type,
        request.params,
        request.quantity,
        request.initial_capital,
        request.rules,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    closed = [t for t in result.trades if not t.is_open]
    if len(closed) < MIN_TRADES:
        raise InvalidStrategyError(
            f"This backtest closed only {len(closed)} trade{'s' if len(closed) != 1 else ''}; Monte Carlo needs at least "
            f"{MIN_TRADES} to say anything. Try a longer period or a more active strategy."
        )

    returns = monte_carlo.account_returns(result.initial_capital, [t.pnl for t in closed])
    analysis = monte_carlo.simulate(result.initial_capital, returns, simulations, method, seed)
    analysis.update(
        symbol=request.symbol.upper(),
        type_label=defn.label,
        initial_capital=result.initial_capital,
        period_start=result.equity_curve[0].date,
        period_end=result.equity_curve[-1].date,
        backtest_return_pct=result.total_return_pct,
        backtest_max_drawdown_pct=result.max_drawdown_pct,
        open_trade_excluded=len(closed) != len(result.trades),
        uses_risk=risk_enabled,
        uses_costs=result.costs_applied,
    )
    return analysis
