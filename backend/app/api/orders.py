from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import BuyOrderRequest, OrderRequest, TradeOut
from ..services import trading_service

router = APIRouter()


@router.post("/orders/buy", response_model=TradeOut)
def buy(order: BuyOrderRequest, db: Session = Depends(get_db)):
    trade = trading_service.execute_buy(
        db, order.symbol, order.quantity, stop_price=order.stop_loss_price, target_price=order.take_profit_price
    )
    return TradeOut.from_trade(trade)


@router.post("/orders/sell", response_model=TradeOut)
def sell(order: OrderRequest, db: Session = Depends(get_db)):
    return TradeOut.from_trade(trading_service.execute_sell(db, order.symbol, order.quantity))
