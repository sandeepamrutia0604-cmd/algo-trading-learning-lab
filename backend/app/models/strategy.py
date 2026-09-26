from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .stock import Stock


class Strategy(Base):
    """One strategy trades one stock. `parameters` holds e.g. {"fast": 20, "slow": 50, "quantity": 10}."""

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    type: Mapped[str] = mapped_column(String(30), default="ma_crossover")
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    parameters: Mapped[dict] = mapped_column(JSON)
    auto_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    stock: Mapped[Stock] = relationship()
