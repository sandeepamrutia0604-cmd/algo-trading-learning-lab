from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import EquityPoint, ExitLevelsRequest, PortfolioOut, PositionOut, StartingCapitalUpdate
from ..services import exit_service
from ..services.portfolio_service import (
    get_equity_curve,
    get_portfolio_summary,
    get_positions_with_pnl,
)
from ..services.trading_service import set_starting_capital

router = APIRouter()


@router.get("/portfolio", response_model=PortfolioOut)
def portfolio_summary(db: Session = Depends(get_db)):
    return get_portfolio_summary(db)


@router.put("/portfolio/starting-capital", response_model=PortfolioOut)
def update_starting_capital(body: StartingCapitalUpdate, db: Session = Depends(get_db)):
    set_starting_capital(db, body.starting_capital)
    return get_portfolio_summary(db)


@router.get("/positions", response_model=list[PositionOut])
def positions(db: Session = Depends(get_db)):
    return get_positions_with_pnl(db)


@router.put("/positions/{symbol}/exits", response_model=PositionOut)
def set_position_exits(symbol: str, body: ExitLevelsRequest, db: Session = Depends(get_db)):
    """Set, change or clear the stop-loss and take-profit on a position you hold."""
    exit_service.set_levels(db, symbol, body.stop_loss_price, body.take_profit_price)
    return next(p for p in get_positions_with_pnl(db) if p["symbol"] == symbol.strip().upper())


@router.get("/portfolio/equity-curve", response_model=list[EquityPoint])
def equity_curve(db: Session = Depends(get_db)):
    return get_equity_curve(db)
