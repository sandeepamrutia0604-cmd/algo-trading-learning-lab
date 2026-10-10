"""Backtest one strategy across several stocks that share one account (see engine/portfolio_backtest.py).
Loads each stock's history the way a one-stock backtest does, runs the engine under the same Risk and cost
settings live trading uses, and adds what only a portfolio has: an equal-weight buy-and-hold baseline and a
breakdown by stock."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from ..adapters import get_market_data_adapter
from ..engine.portfolio_backtest import PortfolioResult, StockSeries, calendar, equal_weight_curve, run_portfolio_backtest
from ..strategies.base import StrategyDef
from . import backtest_metrics, backtest_service, risk_service
from .exceptions import InvalidStrategyError

MIN_STOCKS = 2
MAX_STOCKS = 20


@dataclass
class StockSummary:
    symbol: str
    trades: int  # closed trades
    wins: int
    win_rate_pct: float
    realized_pnl: float
    open_pnl: float  # a position still held at the end, valued at the last close
    total_pnl: float
    contribution_pct: float  # total P&L as a share of the starting capital
    stock_return_pct: float  # simply holding this one stock over the period


@dataclass
class PortfolioRun:
    defn: StrategyDef
    params: dict
    symbols: list[str]
    days: list[date]
    baseline: list[float]
    result: PortfolioResult
    per_stock: list[StockSummary]
    metrics: dict
    risk_enabled: bool
    max_open_positions: int


def clean_symbols(symbols: list[str]) -> list[str]:
    seen: list[str] = []
    for raw in symbols:
        s = raw.strip().upper()
        if s and s not in seen:
            seen.append(s)
    if not MIN_STOCKS <= len(seen) <= MAX_STOCKS:
        raise InvalidStrategyError(f"Choose between {MIN_STOCKS} and {MAX_STOCKS} different stocks")
    return seen


def load_series(db: Session, symbols: list[str], start_date: date | None, end_date: date | None) -> list[StockSeries]:
    adapter = get_market_data_adapter(db, full_history=True)
    out = []
    for symbol in symbols:
        candles = adapter.get_historical_candles(symbol)  # unknown symbol -> StockNotFoundError
        try:
            dates, closes, start_index = backtest_service.window(candles, start_date, end_date)
        except InvalidStrategyError as err:
            if start_date and end_date and start_date > end_date:
                raise
            raise InvalidStrategyError(f"{symbol}: {err}") from None
        opens, highs, lows = backtest_service.ohlc_until(candles, end_date)
        out.append(StockSeries(symbol, dates, closes, opens, highs, lows, start_index))
    return out


def run(
    db: Session,
    symbols: list[str],
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
    risk_free_pct: float = 0.0,
    benchmark: str | None = None,
) -> PortfolioRun:
    backtest_service.check_fill_mode(fill_mode)
    exits = backtest_service.exit_config(stop_loss_pct, take_profit_pct)
    if quantity < 1:
        raise InvalidStrategyError("Quantity must be at least 1")
    if initial_capital <= 0:
        raise InvalidStrategyError("Initial capital must be greater than zero")
    symbols = clean_symbols(symbols)
    defn, clean = backtest_service.resolve_definition(type_key, params, rules)
    stocks = load_series(db, symbols, start_date, end_date)
    risk, costs = backtest_service.run_config(db)
    settings = risk_service.get_settings(db)
    max_open = settings.max_open_positions or 0
    result = run_portfolio_backtest(
        defn, clean, stocks, quantity, initial_capital, risk, costs, fill_mode=fill_mode, exits=exits, max_open_positions=max_open,
    )
    days = calendar(stocks)
    baseline = equal_weight_curve(stocks, days, initial_capital)
    metrics = backtest_metrics.compute(db, result, days, baseline, risk_free_pct, benchmark or None)
    # Positions overlap, so "days held" summed over trades can pass 100%: count the days anything was held instead.
    metrics["days_in_market"] = result.invested_days
    metrics["exposure_pct"] = result.invested_days / len(days) * 100
    return PortfolioRun(defn, clean, [s.symbol for s in sorted(stocks, key=lambda s: s.symbol)], days, baseline, result,
                        summarise(stocks, result), metrics, risk.enabled, max_open)


def summarise(stocks: list[StockSeries], result: PortfolioResult) -> list[StockSummary]:
    last_day = result.equity_curve[-1].date
    rows = []
    for s in sorted(stocks, key=lambda s: s.symbol):
        mine = [t for t in result.trades if t.symbol == s.symbol]
        closed = [t for t in mine if not t.is_open]
        wins = sum(1 for t in closed if t.pnl > 0)
        usable = [i for i, d in enumerate(s.dates) if i >= s.start_index and d <= last_day]
        last_close = s.closes[usable[-1]]
        first_close = s.closes[usable[0]]
        realized = sum(t.pnl for t in closed)
        open_pnl = sum((last_close - t.entry_price) * t.quantity - t.entry_fees for t in mine if t.is_open)
        rows.append(StockSummary(
            symbol=s.symbol,
            trades=len(closed),
            wins=wins,
            win_rate_pct=wins / len(closed) * 100 if closed else 0.0,
            realized_pnl=realized,
            open_pnl=open_pnl,
            total_pnl=realized + open_pnl,
            contribution_pct=(realized + open_pnl) / result.initial_capital * 100,
            stock_return_pct=(last_close / first_close - 1) * 100,
        ))
    return rows
