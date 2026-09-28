from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import RiskSettings
from ..schemas import RiskSettingsOut, RiskSettingsUpdate
from ..services import risk_service

router = APIRouter()


def _out(settings: RiskSettings) -> RiskSettingsOut:
    return RiskSettingsOut(
        enabled=settings.enabled,
        max_risk_per_trade_pct=settings.max_risk_per_trade_pct,
        stop_loss_pct=settings.stop_loss_pct,
        max_open_positions=settings.max_open_positions,
        max_allocation_pct=settings.max_allocation_pct,
    )


@router.get("/risk-settings", response_model=RiskSettingsOut)
def get_risk_settings(db: Session = Depends(get_db)):
    return _out(risk_service.get_settings(db))


@router.patch("/risk-settings", response_model=RiskSettingsOut)
def update_risk_settings(body: RiskSettingsUpdate, db: Session = Depends(get_db)):
    return _out(risk_service.update_settings(db, **body.model_dump(exclude_unset=True)))
