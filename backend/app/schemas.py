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
    source: str = "simulated"
    removable: bool = False  # a practice stock you created, which can be deleted


class PracticeStockRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)  # the format is checked, with a readable message, on create
    name: str | None = Field(default=None, max_length=100)
    starting_price: float = Field(gt=0, le=10_000_000)
    model: MarketModel = "random_walk"
    volatility: float = Field(default=0.02, gt=0, le=0.2)
    trend: float = Field(default=0.0, ge=-0.05, le=0.05)


class StockImportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)  # the format is checked, with a readable message, on import
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


class DataSourceOut(BaseModel):
    key: str
    label: str
    configured: bool
    missing: list[str]  # names of the .env settings still needed, never their values
    note: str


class BrokerImportRequest(BaseModel):
    source: Literal["upstox", "angel_one"]
    symbols: list[str] = Field(min_length=1, max_length=25)
    years: int | None = Field(default=None, ge=1, le=10)
    merge: bool = False


class BrokerImportItem(BaseModel):
    symbol: str
    ok: bool
    name: str | None = None
    candles_stored: int | None = None
    first_date: dt.date | None = None
    last_date: dt.date | None = None
    current_price: float | None = None
    error: str | None = None


class BrokerImportOut(BaseModel):
    source: str
    results: list[BrokerImportItem]
    imported: int
    failed: int
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
    fees: float = 0.0
    market_price: float | None = None
    stop_pct: float | None = None

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
            fees=trade.fees or 0.0,
            market_price=trade.market_price,
            stop_pct=trade.stop_pct,
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
    stop_mode: Literal["fixed", "volatility"] = "fixed"
    volatility_window: int = 20
    volatility_multiplier: float = 2.0


class RiskSettingsUpdate(BaseModel):
    enabled: bool | None = None
    max_risk_per_trade_pct: float | None = Field(default=None, gt=0, le=100)
    stop_loss_pct: float | None = Field(default=None, gt=0, le=100)
    max_open_positions: int | None = Field(default=None, ge=1, le=50)
    max_allocation_pct: float | None = Field(default=None, gt=0, le=100)
    stop_mode: Literal["fixed", "volatility"] | None = None
    volatility_window: int | None = Field(default=None, ge=5, le=100)
    volatility_multiplier: float | None = Field(default=None, ge=0.5, le=10)


class CostSettingsOut(BaseModel):
    enabled: bool
    slippage_pct: float
    brokerage_pct: float
    brokerage_cap: float
    other_charges_pct: float


class CostSettingsUpdate(BaseModel):
    enabled: bool | None = None
    slippage_pct: float | None = Field(default=None, ge=0, le=5)
    brokerage_pct: float | None = Field(default=None, ge=0, le=5)
    brokerage_cap: float | None = Field(default=None, ge=0, le=100_000)
    other_charges_pct: float | None = Field(default=None, ge=0, le=5)


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
    start_date: dt.date | None = None  # first day traded; earlier history only warms the indicators up
    end_date: dt.date | None = None

    @model_validator(mode="after")
    def _dates_in_order(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


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
    stop_pct: float | None = None  # the stop distance this trade was sized and protected with (risk management on)


class BacktestResultOut(BaseModel):
    symbol: str
    type: str
    type_label: str
    params: dict
    rule: str
    quantity: int
    initial_capital: float
    final_capital: float
    period_start: dt.date  # first and last day actually traded
    period_end: dt.date
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    max_drawdown_pct: float
    skipped_buys: int
    stopped_out: int = 0
    risk_managed: bool = False
    volatility_stops: bool = False  # risk management on, with the stop distance set from volatility
    costs_applied: bool = False
    total_fees: float = 0.0
    slippage_cost: float = 0.0
    equity_curve: list[EquityPoint]
    trades: list[BacktestTradeOut]
    series: list[SeriesOut]


class SaveBacktestRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    request: BacktestRequest  # run again on the server and stored, so what is saved is what it computed


class SavedBacktestOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    symbol: str
    type_label: str
    period_start: dt.date
    period_end: dt.date
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    win_rate_pct: float
    max_drawdown_pct: float
    risk_managed: bool
    costs_applied: bool


class SavedBacktestDetailOut(SavedBacktestOut):
    request: BacktestRequest
    result: BacktestResultOut


class AxisRange(BaseModel):
    param: str = Field(min_length=1, max_length=40)
    low: float
    high: float
    step: float = Field(gt=0)


class OptimiseRequest(BaseModel):
    symbol: str
    type: str
    params: dict[str, float] = {}  # settings that stay fixed while the others are swept
    x: AxisRange
    y: AxisRange | None = None
    metric: Literal["return", "risk_adjusted"] = "return"
    quantity: int = Field(default=10, ge=1, le=100000)
    initial_capital: float = Field(default=100_000.0, gt=0, le=1_000_000_000)
    train_start: dt.date | None = None
    train_end: dt.date | None = None
    test_start: dt.date | None = None
    test_end: dt.date | None = None


class GridCellOut(BaseModel):
    score: float
    return_pct: float
    max_drawdown_pct: float
    trades: int


class GridAxisOut(BaseModel):
    name: str
    label: str
    values: list[float]


class GridPeriodOut(BaseModel):
    start: dt.date
    end: dt.date
    buy_hold_pct: float
    cells: list[list[GridCellOut | None]]  # rows follow the y values (one row if there is no y), columns the x values


class BestSettingsOut(BaseModel):
    params: dict
    train: GridCellOut
    test: GridCellOut | None = None
    test_rank: int | None = None  # 1 = the training winner was also the best on the test period
    test_valid: int | None = None
    test_median_score: float | None = None


class OptimiseOut(BaseModel):
    symbol: str
    type: str
    type_label: str
    metric: str
    x: GridAxisOut
    y: GridAxisOut | None = None
    train: GridPeriodOut
    test: GridPeriodOut | None = None
    best: BestSettingsOut
    combinations: int
    valid: int
    uses_risk: bool
    uses_costs: bool


class WalkForwardRequest(BaseModel):
    symbol: str
    type: str
    params: dict[str, float] = {}
    x: AxisRange
    y: AxisRange | None = None
    metric: Literal["return", "risk_adjusted"] = "return"
    quantity: int = Field(default=10, ge=1, le=100000)
    initial_capital: float = Field(default=100_000.0, gt=0, le=1_000_000_000)
    folds: int = Field(default=5, ge=2, le=10)
    train_ratio: float = Field(default=3.0, ge=1.0, le=10.0)  # training days per test day
    mode: Literal["rolling", "anchored"] = "rolling"
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class WalkForwardFoldOut(BaseModel):
    index: int
    train_start: dt.date
    train_end: dt.date
    test_start: dt.date
    test_end: dt.date
    params: dict
    train: GridCellOut
    test: GridCellOut
    test_buy_hold_pct: float
    test_rank: int
    test_valid: int
    test_median_score: float
    train_cells: list[list[GridCellOut | None]]  # the whole grid on this fold's training window
    test_cells: list[list[GridCellOut | None]]  # and on its unseen test window


class WalkForwardSummaryOut(BaseModel):
    folds: int
    avg_train_return_pct: float
    avg_test_return_pct: float
    efficiency_pct: float | None = None  # average test return as a share of average training return
    oos_return_pct: float  # the test windows chained end to end
    oos_buy_hold_pct: float
    oos_max_drawdown_pct: float
    profitable_folds: int
    beat_buy_hold_folds: int
    distinct_settings: int
    tested_from: dt.date
    tested_to: dt.date


class WalkForwardEquityOut(BaseModel):
    dates: list[dt.date]
    strategy: list[float]
    buy_hold: list[float]


class WalkForwardOut(BaseModel):
    symbol: str
    type: str
    type_label: str
    metric: str
    mode: str
    train_ratio: float
    x: GridAxisOut
    y: GridAxisOut | None = None
    folds: list[WalkForwardFoldOut]
    summary: WalkForwardSummaryOut
    equity: WalkForwardEquityOut
    combinations: int
    uses_risk: bool
    uses_costs: bool


class MonteCarloRequest(BaseModel):
    request: BacktestRequest  # the backtest whose trades are re-played
    simulations: int = Field(default=1000, ge=100, le=5000)
    method: Literal["shuffle", "bootstrap"] = "bootstrap"
    seed: int | None = None  # for a repeatable run; omit for a fresh one each time


class McHistogramOut(BaseModel):
    edges: list[float]
    counts: list[int]


class McDistributionOut(BaseModel):
    mean: float
    min: float
    max: float
    percentiles: dict[str, float]  # "5", "25", "50", "75", "95"
    histogram: McHistogramOut


class McOriginalOut(BaseModel):
    return_pct: float
    max_drawdown_pct: float


class McExceedOut(BaseModel):
    threshold: int
    pct: float


class McFanOut(BaseModel):
    trade_numbers: list[int]
    bands: dict[str, list[float]]  # account value at each kept trade number, per percentile
    original: list[float]


class MonteCarloOut(BaseModel):
    symbol: str
    type_label: str
    method: str
    simulations: int
    trade_count: int
    initial_capital: float
    period_start: dt.date
    period_end: dt.date
    original: McOriginalOut  # the actual trades in their actual order, between closed trades
    backtest_return_pct: float  # the backtest itself, marked to market daily
    backtest_max_drawdown_pct: float
    final_return: McDistributionOut
    max_drawdown: McDistributionOut
    probability_of_loss_pct: float
    drawdown_exceeds_pct: list[McExceedOut]
    original_drawdown_worse_than_pct: float
    original_return_better_than_pct: float
    fan: McFanOut
    open_trade_excluded: bool
    uses_risk: bool
    uses_costs: bool
