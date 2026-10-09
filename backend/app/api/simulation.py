from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.alert_service import delete_all as delete_all_alerts
from ..services.market_service import reset_market
from ..services.strategy_service import clear_all_signals
from ..services.trading_service import reset_simulation

router = APIRouter()


@router.post("/reset")
def reset(db: Session = Depends(get_db)):
    clear_all_signals(db)
    delete_all_alerts(db)
    reset_simulation(db)
    reset_market(db)
    return {"status": "reset"}
