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
            source=trade.strategy.name if trade.strategy else "Manual",
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
    fast: int = Field(default=20, ge=2, le=500)
    slow: int = Field(default=50, ge=3, le=500)
    quantity: int = Field(default=10, ge=1, le=100000)
    auto_trade: bool = False
    name: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def fast_below_slow(self):
        if self.fast >= self.slow:
            raise ValueError("fast period must be smaller than slow period")
        return self


class StrategyUpdate(BaseModel):
    fast: int | None = Field(default=None, ge=2, le=500)
    slow: int | None = Field(default=None, ge=3, le=500)
    quantity: int | None = Field(default=None, ge=1, le=100000)
    auto_trade: bool | None = None
    name: str | None = Field(default=None, max_length=120)


class StrategyOut(BaseModel):
    id: int
    name: str
    description: str | None
    type: str
    symbol: str
    fast: int
    slow: int
    quantity: int
    auto_trade: bool
    created_at: datetime
    signal_count: int
    buy_count: int
    sell_count: int
    held: int


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
