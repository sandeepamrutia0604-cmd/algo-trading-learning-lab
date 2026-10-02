import datetime as dt
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MarketModel = Literal["random_walk", "trending", "volatile", "sideways"]


class StockOut(BaseModel):
    symbol: str
    name: str
    starting_price: float
    current_price: float
    previous_close: float | None = None
    recent_closes: list[float] = []


class StockImportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9&-]+$")
    name: str | None = Field(default=None, max_length=100)
    csv_text: str = Field(min_length=1, max_length=5_000_000)
    replace: bool = False


class StockImportOut(BaseModel):
    symbol: str
    name: str
    created: bool
    candles_read: int
    candles_stored: int
    first_date: dt.date
    last_date: dt.date
    current_price: float
    market_date: dt.date | None = None


class OrderRequest(BaseModel):
    symbol: str
    quantity: int = Field(gt=0)


class TradeOut(BaseModel):
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: datetime
    reason: str | None = None
    market_date: dt.date | None = None
    realized_pnl: float | None = None
    strategy_id: int | None = None
    source: str = "Manual"

    @classmethod
    def from_trade(cls, trade) -> "TradeOut":
        source = trade.strategy.name if trade.strategy else "Manual"
        if trade.reason and "stop-loss" in trade.reason.lower():
            source += " · stop-loss"
        return cls(
            symbol=trade.stock.symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=trade.price,
            timestamp=trade.timestamp,
            reason=trade.reason,
            market_date=trade.market_date,
            realized_pnl=trade.realized_pnl,
            strategy_id=trade.strategy_id,
            source=source,
        )


class PositionOut(BaseModel):
    symbol: str
    name: str
    quantity: int
    average_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    day_pnl: float


class PortfolioOut(BaseModel):
    cash: float
    invested: float
    market_value: float
    portfolio_value: float
    unrealized_pnl: float
    realized_pnl: float
    day_pnl: float
    total_pnl: float
    return_pct: float
    starting_capital: float


class StartingCapitalUpdate(BaseModel):
    starting_capital: float = Field(gt=0, le=100_000_000)


class CandleOut(BaseModel):
    date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketConfigIn(BaseModel):
    model: MarketModel
    volatility: float = Field(gt=0, le=0.2)
    trend: float = Field(ge=-0.05, le=0.05)


class MarketConfigOut(MarketConfigIn):
    symbol: str


class GenerateRequest(BaseModel):
    days: int = Field(default=60, ge=2, le=1000)
    seed: int | None = None


class AdvanceRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=60)


class MarketStatusOut(BaseModel):
    date: dt.date | None
    events: list[str] = []
    reached_end: bool = False


class IndicatorPoint(BaseModel):
    date: dt.date
    value: float


class IndicatorsOut(BaseModel):
    sma: dict[str, list[IndicatorPoint]]


class EquityPoint(BaseModel):
    date: dt.date
    value: float


class StrategyCreate(BaseModel):
    symbol: str
    type: str = "ma_crossover"
    params: dict[str, float] = {}
    rules: dict | None = None
    quantity: int = Field(default=10, ge=1, le=100000)
    auto_trade: bool = False
    name: str | None = Field(default=None, max_length=120)


class StrategyUpdate(BaseModel):
    params: dict[str, float] | None = None
    rules: dict | None = None
    quantity: int | None = Field(default=None, ge=1, le=100000)
    auto_trade: bool | None = None
    name: str | None = Field(default=None, max_length=120)


class StrategyOut(BaseModel):
    id: int
    name: str
    description: str | None
    type: str
    type_label: str
    symbol: str
    params: dict
    param_summary: str
    rules: dict | None = None
    quantity: int
    auto_trade: bool
    created_at: datetime
    signal_count: int
    buy_count: int
    sell_count: int
    held: int


class ParamSpecOut(BaseModel):
    name: str
    label: str
    default: float
    min: float
    max: float
    step: float
    kind: str


class StrategyTypeOut(BaseModel):
    key: str
    label: str
    summary: str
    works_best: str
    struggles: str
    entry_text: str
    exit_text: str
    params: list[ParamSpecOut]


class SeriesOut(BaseModel):
    name: str
    panel: str
    color: str
    dash: str
    width: float
    fill_to_previous: bool
    y_range: list[float] | None = None
    points: list["IndicatorPoint"]


class SignalOut(BaseModel):
    id: int
    strategy_id: int
    strategy_name: str
    symbol: str
    date: dt.date
    signal: str
    price: float
    reason: str
    details: dict
    executed: bool
    note: str | None = None
    trade_quantity: int | None = None
    trade_price: float | None = None
    realized_pnl: float | None = None


class RiskSettingsOut(BaseModel):
    enabled: bool
    max_risk_per_trade_pct: float
    stop_loss_pct: float
    max_open_positions: int
    max_allocation_pct: float


class RiskSettingsUpdate(BaseModel):
    enabled: bool | None = None
    max_risk_per_trade_pct: float | None = Field(default=None, gt=0, le=100)
    stop_loss_pct: float | None = Field(default=None, gt=0, le=100)
    max_open_positions: int | None = Field(default=None, ge=1, le=50)
    max_allocation_pct: float | None = Field(default=None, gt=0, le=100)


class TradeStatsOut(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    avg_win: float
    avg_loss: float
    profit_factor: float | None = None


class MonthlyReturnOut(BaseModel):
    month: str
    return_pct: float


class StrategyPerformanceOut(TradeStatsOut):
    strategy_id: int | None
    name: str
    total_pnl: float


class PerformanceOut(BaseModel):
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    trade_stats: TradeStatsOut
    equity_curve: list[EquityPoint]
    drawdown_curve: list[EquityPoint]
    monthly_returns: list[MonthlyReturnOut]
    trade_pnls: list[float]
    by_strategy: list[StrategyPerformanceOut]


class BacktestRequest(BaseModel):
    symbol: str
    type: str = "ma_crossover"
    params: dict[str, float] = {}
    rules: dict | None = None
    quantity: int = Field(default=10, ge=1, le=100000)
    initial_capital: float = Field(default=100_000.0, gt=0, le=1_000_000_000)


class BacktestTradeOut(BaseModel):
    entry_date: dt.date
    entry_price: float
    quantity: int
    exit_date: dt.date | None = None
    exit_price: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    open: bool
    stopped_out: bool = False


class BacktestResultOut(BaseModel):
    symbol: str
    type: str
    type_label: str
    params: dict
    rule: str
    quantity: int
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    max_drawdown_pct: float
    skipped_buys: int
    stopped_out: int = 0
    risk_managed: bool = False
    equity_curve: list[EquityPoint]
    trades: list[BacktestTradeOut]
    series: list[SeriesOut]
