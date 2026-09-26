import datetime as dt
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

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


class IndicatorPoint(BaseModel):
    date: dt.date
    value: float


class IndicatorsOut(BaseModel):
    sma: dict[str, list[IndicatorPoint]]


class EquityPoint(BaseModel):
    date: dt.date
    value: float
