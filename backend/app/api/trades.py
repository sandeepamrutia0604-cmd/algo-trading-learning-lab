from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Trade
from ..schemas import TradeOut

router = APIRouter()


@router.get("/trades", response_model=list[TradeOut])
def list_trades(db: Session = Depends(get_db)):
    trades = db.query(Trade).order_by(Trade.timestamp.desc(), Trade.id.desc()).all()
    return [TradeOut.from_trade(t) for t in trades]
