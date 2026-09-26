from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Stock
from ..schemas import StockOut
from ..services import market_service

router = APIRouter()


@router.get("/stocks", response_model=list[StockOut])
def list_stocks(db: Session = Depends(get_db)):
    result = []
    for stock in db.query(Stock).order_by(Stock.symbol).all():
        closes = market_service.recent_closes(db, stock.id)
        result.append(
            StockOut(
                symbol=stock.symbol,
                name=stock.name,
                starting_price=stock.starting_price,
                current_price=stock.current_price,
                previous_close=closes[-2] if len(closes) >= 2 else None,
                recent_closes=closes,
            )
        )
    return result
