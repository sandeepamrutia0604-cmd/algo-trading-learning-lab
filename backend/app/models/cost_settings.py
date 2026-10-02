from sqlalchemy import Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class CostSettings(Base):
    """Trading-cost simulation (slippage + brokerage + taxes). Single-user local app: this
    table holds exactly one row. Off by default, so trades fill at the quoted price for free,
    exactly as before."""

    __tablename__ = "cost_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    slippage_pct: Mapped[float] = mapped_column(Float, default=0.05)
    brokerage_pct: Mapped[float] = mapped_column(Float, default=0.03)
    brokerage_cap: Mapped[float] = mapped_column(Float, default=20.0)
    other_charges_pct: Mapped[float] = mapped_column(Float, default=0.1)
