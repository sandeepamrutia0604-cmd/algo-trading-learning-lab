from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .stock import Stock
from .strategy import Strategy
from .trade import Trade


class Signal(Base):
    """A BUY/SELL decision made by a strategy on one market day, with the reason behind it."""

    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("strategy_id", "market_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    market_date: Mapped[date] = mapped_column(Date)
    signal: Mapped[str] = mapped_column(String(4))  # "BUY" or "SELL"
    price: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(400))
    details: Mapped[dict] = mapped_column(JSON)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    strategy: Mapped[Strategy] = relationship()
    stock: Mapped[Stock] = relationship()
    trade: Mapped[Trade | None] = relationship()
