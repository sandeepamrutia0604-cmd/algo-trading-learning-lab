from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Trade
from ..schemas import TradeOut

router = APIRouter()


@router.get("/trades", response_model=list[TradeOut])
def list_trades(db: Session = Depends(get_db)):
    trades = db.query(Trade).order_by(Trade.timestamp.desc()).all()
    return [
        TradeOut(
            symbol=t.stock.symbol,
            side=t.side,
            quantity=t.quantity,
            price=t.price,
            timestamp=t.timestamp,
            reason=t.reason,
        )
        for t in trades
    ]
