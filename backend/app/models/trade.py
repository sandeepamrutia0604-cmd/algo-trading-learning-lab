from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .stock import Stock
from .strategy import Strategy


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    side: Mapped[str] = mapped_column(String(4))  # "BUY" or "SELL"
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)  # the fill price, after any slippage
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    market_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"), nullable=True)
    # Brokerage + taxes paid on this order, and the quoted price before slippage (NULL on
    # trades from before trading costs existed).
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    # The stop distance (percent below the entry) a strategy's BUY was sized and protected with,
    # fixed at entry: a volatility-based stop must not drift as the stock's volatility changes
    # (NULL for manual trades and trades from before this existed; the fixed setting applies).
    stop_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    stock: Mapped[Stock] = relationship()
    strategy: Mapped[Strategy | None] = relationship()
