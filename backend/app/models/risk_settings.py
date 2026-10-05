from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class RiskSettings(Base):
    """Single-user local app: this table holds exactly one row."""

    __tablename__ = "risk_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    max_risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=2.0)
    stop_loss_pct: Mapped[float] = mapped_column(Float, default=5.0)
    max_open_positions: Mapped[int] = mapped_column(Integer, default=5)
    max_allocation_pct: Mapped[float] = mapped_column(Float, default=20.0)
    # How the stop distance is chosen: "fixed" uses stop_loss_pct; "volatility" uses
    # volatility_multiplier x the last volatility_window days' daily volatility (stop_loss_pct is
    # then only the fallback while there is too little history). See engine/risk_math.py.
    stop_mode: Mapped[str] = mapped_column(String(12), default="fixed")
    volatility_window: Mapped[int] = mapped_column(Integer, default=20)
    volatility_multiplier: Mapped[float] = mapped_column(Float, default=2.0)
