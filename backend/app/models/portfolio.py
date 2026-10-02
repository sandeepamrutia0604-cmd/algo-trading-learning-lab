from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base

INITIAL_VIRTUAL_CASH = 100_000.0


class Portfolio(Base):
    """Single-user local app: this table holds exactly one row."""

    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(primary_key=True)
    virtual_cash: Mapped[float] = mapped_column(Float, default=INITIAL_VIRTUAL_CASH)
    # The bankroll a reset restores and P&L/return % is measured against. Defaults to
    # INITIAL_VIRTUAL_CASH but is user-editable (see trading_service.set_starting_capital) --
    # useful once real, higher-priced stocks are in play and 100,000 buys very little of them.
    starting_capital: Mapped[float] = mapped_column(Float, default=INITIAL_VIRTUAL_CASH)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    # The market clock: the simulated "today". Every stock only shows candles up to this date,
    # which is how an imported stock's real history replays forward one day at a time (see
    # services/market_service.py). NULL until the market is first started.
    market_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
