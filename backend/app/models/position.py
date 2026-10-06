from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .stock import Stock


class Position(Base):
    """One row per stock currently held. Rows are deleted when quantity hits 0."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), unique=True)
    quantity: Mapped[int] = mapped_column(Integer)
    average_price: Mapped[float] = mapped_column(Float)
    # Protective exits for the whole position (see engine/exit_math.py): sell if the price falls
    # to stop_price or rises to target_price. NULL means no exit of that kind.
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    stock: Mapped[Stock] = relationship()
