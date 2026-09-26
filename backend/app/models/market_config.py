from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .stock import Stock


class MarketConfig(Base):
    """Price-model settings for one stock. Applied when history is generated or advanced."""

    __tablename__ = "market_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), unique=True)
    model: Mapped[str] = mapped_column(String(20))
    volatility: Mapped[float] = mapped_column(Float)
    trend: Mapped[float] = mapped_column(Float)

    stock: Mapped[Stock] = relationship()
