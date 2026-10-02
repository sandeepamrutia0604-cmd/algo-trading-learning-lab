from sqlalchemy.orm import Session

from ..engine.cost_math import CostConfig
from ..models import CostSettings


def get_settings(db: Session) -> CostSettings:
    settings = db.query(CostSettings).first()
    if settings is None:
        raise RuntimeError("CostSettings not seeded — call ensure_seed_data() at startup")
    return settings


def update_settings(db: Session, **fields) -> CostSettings:
    settings = get_settings(db)
    for key, value in fields.items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings


def config(db: Session) -> CostConfig:
    """The saved settings as the plain value the pure cost formulas take."""
    settings = get_settings(db)
    return CostConfig(
        enabled=settings.enabled,
        slippage_pct=settings.slippage_pct,
        brokerage_pct=settings.brokerage_pct,
        brokerage_cap=settings.brokerage_cap,
        other_charges_pct=settings.other_charges_pct,
    )
