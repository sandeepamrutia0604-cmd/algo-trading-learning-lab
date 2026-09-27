from datetime import date

from sqlalchemy.orm import Session

from ..engine.backtest import BacktestResult, run_backtest
from ..strategies.base import StrategyDef
from ..strategies.registry import get_definition
from . import market_service
from .exceptions import InvalidStrategyError


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


def run(
    db: Session,
    symbol: str,
    type_key: str,
    params: dict | None,
    quantity: int,
    initial_capital: float,
) -> tuple[StrategyDef, dict, list[date], list[float], BacktestResult]:
    if quantity < 1:
        raise InvalidStrategyError("Quantity must be at least 1")
    if initial_capital <= 0:
        raise InvalidStrategyError("Initial capital must be greater than zero")

    defn = _definition(type_key)
    clean = _normalize(defn, params)
    prices = market_service.get_prices(db, symbol)
    if len(prices) < 2:
        raise InvalidStrategyError("Not enough price history to run a backtest")

    dates = [p.timestamp.date() for p in prices]
    closes = [p.close for p in prices]
    result = run_backtest(defn, clean, dates, closes, quantity, initial_capital)
    return defn, clean, dates, closes, result
