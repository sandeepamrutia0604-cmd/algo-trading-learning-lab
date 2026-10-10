from datetime import date

from sqlalchemy.orm import Session

from ..adapters import get_market_data_adapter
from ..engine import rule_engine
from ..engine.backtest import FILL_MODES, BacktestResult, ExitConfig, RiskConfig, run_backtest
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


def resolve_definition(type_key: str, params: dict | None, rules: dict | None = None) -> tuple[StrategyDef, dict]:
    """The strategy definition and its cleaned-up parameters for a request naming a built-in type
    (with its parameters) or a custom rule set. Shared by backtests and the scanner."""
    if type_key == CUSTOM_TYPE:
        return rule_engine.build_definition(_validated_rules(rules)), {}
    defn = _definition(type_key)
    return defn, _normalize(defn, params)


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


def ohlc_until(candles: list, end_date: date | None) -> tuple[list[float], list[float], list[float]]:
    """(opens, highs, lows) lined up with the dates `window` returns for the same `end_date`: what fills at
    the next open and the order-level stop-loss and take-profit need besides the closes."""
    kept = [c for c in candles if not end_date or c.date <= end_date]
    return [c.open for c in kept], [c.high for c in kept], [c.low for c in kept]


def exit_config(stop_loss_pct: float | None, take_profit_pct: float | None) -> ExitConfig:
    """The order-level exits a request asks for (percentages of each trade's entry price), or none."""
    if stop_loss_pct is not None and not 0 < stop_loss_pct < 100:
        raise InvalidStrategyError("The stop-loss must be more than 0% and less than 100% below the entry price")
    if take_profit_pct is not None and not 0 < take_profit_pct <= 1000:
        raise InvalidStrategyError("The take-profit must be more than 0% above the entry price (up to 1000%)")
    return ExitConfig(stop_pct=stop_loss_pct, target_pct=take_profit_pct)


def check_fill_mode(fill_mode: str) -> None:
    if fill_mode not in FILL_MODES:
        raise InvalidStrategyError(f"Unknown fill mode '{fill_mode}'. Choose one of: {', '.join(FILL_MODES)}")


def run_config(db: Session) -> tuple[RiskConfig, CostConfig]:
    """The risk and cost settings a backtest runs under (the same ones live auto-trading uses)."""
    settings = risk_service.get_settings(db)
    risk = RiskConfig(
        enabled=settings.enabled,
        max_risk_per_trade_pct=settings.max_risk_per_trade_pct,
        stop_loss_pct=settings.stop_loss_pct,
        max_allocation_pct=settings.max_allocation_pct,
        stop_mode=settings.stop_mode or "fixed",
        volatility_window=settings.volatility_window or 20,
        volatility_multiplier=settings.volatility_multiplier or 2.0,
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
    fill_mode: str = "signal_close",
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
) -> tuple[StrategyDef, dict, list[date], list[float], BacktestResult, bool]:
    """Returns (defn, params, dates, closes, result, risk_enabled). The backtest applies the
    same RiskSettings (position sizing, stop-loss, max allocation) live auto-trading would,
    so a backtest result reflects what auto-trading this strategy would actually have done.

    `start_date`/`end_date` (both optional, inclusive) pick the period that is traded. History
    after `end_date` is dropped. History before `start_date` is kept only to warm the
    indicators up, so a short window isn't spent waiting for a slow average to form; `dates`
    and `closes` still include those warm-up days, and the result's equity curve starts on
    the first traded day.

    `fill_mode` is when decisions are carried out: "signal_close" (at the close of the day a signal
    appears) or "next_open" (at the next day's opening price); see engine/backtest.py.

    `stop_loss_pct` / `take_profit_pct` (optional) are order-level exits, as percentages of each trade's entry
    price, checked every day against that day's low and high like the exits on a live order."""
    check_fill_mode(fill_mode)
    exits = exit_config(stop_loss_pct, take_profit_pct)
    if quantity < 1:
        raise InvalidStrategyError("Quantity must be at least 1")
    if initial_capital <= 0:
        raise InvalidStrategyError("Initial capital must be greater than zero")

    defn, clean = resolve_definition(type_key, params, rules)
    candles = get_market_data_adapter(db, full_history=True).get_historical_candles(symbol)
    if len(candles) < 2:
        raise InvalidStrategyError("Not enough price history to run a backtest")
    dates, closes, start_index = window(candles, start_date, end_date)
    risk, costs = run_config(db)
    opens, highs, lows = ohlc_until(candles, end_date)
    result = run_backtest(
        defn, clean, dates, closes, quantity, initial_capital, risk, costs, start_index=start_index, fill_mode=fill_mode,
        opens=opens, highs=highs, lows=lows, exits=exits,
    )
    return defn, clean, dates, closes, result, risk.enabled
