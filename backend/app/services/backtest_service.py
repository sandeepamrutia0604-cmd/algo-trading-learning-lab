from datetime import date

from sqlalchemy.orm import Session

from ..engine import rule_engine
from ..engine.backtest import BacktestResult, RiskConfig, run_backtest
from ..strategies.base import StrategyDef
from ..strategies.registry import get_definition
from . import market_service, risk_service
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


def run(
    db: Session,
    symbol: str,
    type_key: str,
    params: dict | None,
    quantity: int,
    initial_capital: float,
    rules: dict | None = None,
) -> tuple[StrategyDef, dict, list[date], list[float], BacktestResult, bool]:
    """Returns (defn, params, dates, closes, result, risk_enabled). The backtest applies the
    same RiskSettings (position sizing, stop-loss, max allocation) live auto-trading would,
    so a backtest result reflects what auto-trading this strategy would actually have done."""
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
    prices = market_service.get_prices(db, symbol)
    if len(prices) < 2:
        raise InvalidStrategyError("Not enough price history to run a backtest")

    dates = [p.timestamp.date() for p in prices]
    closes = [p.close for p in prices]
    settings = risk_service.get_settings(db)
    risk = RiskConfig(
        enabled=settings.enabled,
        max_risk_per_trade_pct=settings.max_risk_per_trade_pct,
        stop_loss_pct=settings.stop_loss_pct,
        max_allocation_pct=settings.max_allocation_pct,
    )
    result = run_backtest(defn, clean, dates, closes, quantity, initial_capital, risk)
    return defn, clean, dates, closes, result, settings.enabled
