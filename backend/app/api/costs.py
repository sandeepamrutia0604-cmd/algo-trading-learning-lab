from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CostSettings
from ..schemas import CostSettingsOut, CostSettingsUpdate
from ..services import cost_service

router = APIRouter()


def _out(settings: CostSettings) -> CostSettingsOut:
    return CostSettingsOut(
        enabled=settings.enabled,
        slippage_pct=settings.slippage_pct,
        brokerage_pct=settings.brokerage_pct,
        brokerage_cap=settings.brokerage_cap,
        other_charges_pct=settings.other_charges_pct,
    )


@router.get("/cost-settings", response_model=CostSettingsOut)
def get_cost_settings(db: Session = Depends(get_db)):
    return _out(cost_service.get_settings(db))


@router.patch("/cost-settings", response_model=CostSettingsOut)
def update_cost_settings(body: CostSettingsUpdate, db: Session = Depends(get_db)):
    return _out(cost_service.update_settings(db, **body.model_dump(exclude_unset=True)))
