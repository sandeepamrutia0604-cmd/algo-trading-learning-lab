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

    model_config = {"from_attributes": True}


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


class PositionOut(BaseModel):
    symbol: str
    name: str
    quantity: int
    average_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float


class PortfolioOut(BaseModel):
    cash: float
    invested: float
    market_value: float
    portfolio_value: float
    unrealized_pnl: float
    realized_pnl: float
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
