from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.trading_service import reset_simulation

router = APIRouter()


@router.post("/reset")
def reset(db: Session = Depends(get_db)):
    reset_simulation(db)
    return {"status": "reset"}
