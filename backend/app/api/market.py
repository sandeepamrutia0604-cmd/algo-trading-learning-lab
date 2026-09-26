from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketConfig, Stock
from ..schemas import (
    AdvanceRequest,
    CandleOut,
    GenerateRequest,
    MarketConfigIn,
    MarketConfigOut,
    MarketStatusOut,
)
from ..services import market_service

router = APIRouter()


def _config_out(config: MarketConfig) -> MarketConfigOut:
    return MarketConfigOut(
        symbol=config.stock.symbol,
        model=config.model,
        volatility=config.volatility,
        trend=config.trend,
    )


@router.get("/stocks/{symbol}/prices", response_model=list[CandleOut])
def prices(symbol: str, limit: int | None = Query(default=None, ge=1, le=5000), db: Session = Depends(get_db)):
    rows = market_service.get_prices(db, symbol, limit)
    return [
        CandleOut(
            date=r.timestamp.date(), open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume
        )
        for r in rows
    ]


@router.get("/market/config", response_model=list[MarketConfigOut])
def list_config(db: Session = Depends(get_db)):
    stocks = db.query(Stock).order_by(Stock.symbol).all()
    configs = [market_service.get_config(db, s) for s in stocks]
    db.commit()
    return [_config_out(c) for c in configs]


@router.put("/market/config/{symbol}", response_model=MarketConfigOut)
def set_config(symbol: str, body: MarketConfigIn, db: Session = Depends(get_db)):
    config = market_service.update_config(db, symbol, body.model, body.volatility, body.trend)
    return _config_out(config)


@router.post("/market/generate", response_model=MarketStatusOut)
def generate(body: GenerateRequest, db: Session = Depends(get_db)):
    market_service.generate_all(db, body.days, body.seed)
    return MarketStatusOut(date=market_service.latest_market_date(db))


@router.post("/market/advance", response_model=MarketStatusOut)
def advance(body: AdvanceRequest, db: Session = Depends(get_db)):
    market_service.advance(db, body.days)
    return MarketStatusOut(date=market_service.latest_market_date(db))
