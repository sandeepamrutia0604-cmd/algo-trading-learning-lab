from datetime import date

from sqlalchemy.orm import Session

from ..adapters import get_market_data_adapter
from ..engine import rule_engine
from ..engine.backtest import BacktestResult, RiskConfig, run_backtest
from ..engine.cost_math import CostConfig
from ..strategies.base import StrategyDef
from ..strategies.registry import get_definition
from . import cost_service, risk_service
from .exceptions import InvalidStrategyError

CUSTOM_TYPE = "custom"


def _definition(type_key: str) -> StrategyDef:
    try:
        return get_definition(type_key)
    except ValueError as exc:
        raise InvalidStrategyError(str(exc)) from exc


def _normalize(defn: StrategyDef, params: dict | None) -> dict:
    try:
        return defn.normalize(params)
    except ValueError as exc:
        raise InvalidStrategyError(str(exc)) from exc


def _validated_rules(rules: dict | None) -> dict:
    try:
        rule_engine.validate_rules(rules)
    except ValueError as exc:
        raise InvalidStrategyError(str(exc)) from exc
    return rules


def window(candles: list, start_date: date | None, end_date: date | None) -> tuple[list[date], list[float], int]:
    """Cut `candles` to the traded period: (dates, closes, start_index). Candles after `end_date`
    are dropped; candles before `start_date` stay (the indicators warm up on them) and
    `start_index` says where trading begins. Shared by backtests and the optimiser, so a date
    range means exactly the same thing in both."""
    if start_date and end_date and start_date > end_date:
        raise InvalidStrategyError("The start date must be on or before the end date")
    if end_date:
        candles = [c for c in candles if c.date <= end_date]
    start_index = next((i for i, c in enumerate(candles) if not start_date or c.date >= start_date), len(candles))
    if len(candles) - start_index < 2:
        raise InvalidStrategyError("Fewer than 2 trading days of price history fall in that date range")
    return [c.date for c in candles], [c.close for c in candles], start_index


def run_config(db: Session) -> tuple[RiskConfig, CostConfig]:
    """The risk and cost settings a backtest runs under (the same ones live auto-trading uses)."""
    settings = risk_service.get_settings(db)
    risk = RiskConfig(
        enabled=settings.enabled,
        max_risk_per_trade_pct=settings.max_risk_per_trade_pct,
        stop_loss_pct=settings.stop_loss_pct,
        max_allocation_pct=settings.max_allocation_pct,
    )
    return risk, cost_service.config(db)


def run(
    db: Session,
    symbol: str,
    type_key: str,
    params: dict | None,
    quantity: int,
    initial_capital: float,
    rules: dict | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[StrategyDef, dict, list[date], list[float], BacktestResult, bool]:
    """Returns (defn, params, dates, closes, result, risk_enabled). The backtest applies the
    same RiskSettings (position sizing, stop-loss, max allocation) live auto-trading would,
    so a backtest result reflects what auto-trading this strategy would actually have done.

    `start_date`/`end_date` (both optional, inclusive) pick the period that is traded. History
    after `end_date` is dropped. History before `start_date` is kept only to warm the
    indicators up, so a short window isn't spent waiting for a slow average to form; `dates`
    and `closes` still include those warm-up days, and the result's equity curve starts on
    the first traded day."""
    if quantity < 1:
        raise InvalidStrategyError("Quantity must be at least 1")
    if initial_capital <= 0:
        raise InvalidStrategyError("Initial capital must be greater than zero")

    if type_key == CUSTOM_TYPE:
        clean_rules = _validated_rules(rules)
        defn = rule_engine.build_definition(clean_rules)
        clean = {}
    else:
        defn = _definition(type_key)
        clean = _normalize(defn, params)
    candles = get_market_data_adapter(db, full_history=True).get_historical_candles(symbol)
    if len(candles) < 2:
        raise InvalidStrategyError("Not enough price history to run a backtest")
    dates, closes, start_index = window(candles, start_date, end_date)
    risk, costs = run_config(db)
    result = run_backtest(defn, clean, dates, closes, quantity, initial_capital, risk, costs, start_index=start_index)
    return defn, clean, dates, closes, result, risk.enabled
