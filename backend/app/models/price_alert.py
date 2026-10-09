from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class PriceAlert(Base):
    """"Tell me when SYMBOL goes above / below LEVEL." It only notifies, it never trades. An alert
    fires once (`active` turns False and the day and price are kept) and can be re-armed.
    `symbol` is plain text, not a foreign key, so an alert outlives a deleted practice stock."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # "above" or "below"
    level: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    triggered_price: Mapped[float | None] = mapped_column(Float, nullable=True)
