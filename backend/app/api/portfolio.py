from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import PortfolioOut, PositionOut
from ..services.portfolio_service import get_portfolio_summary, get_positions_with_pnl

router = APIRouter()


@router.get("/portfolio", response_model=PortfolioOut)
def portfolio_summary(db: Session = Depends(get_db)):
    return get_portfolio_summary(db)


@router.get("/positions", response_model=list[PositionOut])
def positions(db: Session = Depends(get_db)):
    return get_positions_with_pnl(db)
