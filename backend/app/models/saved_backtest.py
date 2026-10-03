from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, deferred, mapped_column

from ..db import Base


class SavedBacktest(Base):
    """A backtest you chose to keep. The headline numbers get their own columns so the list can
    be shown cheaply; `request` is exactly what was run (so it can be loaded back into the
    builder and re-run), and `result` is the full output, equity curve and trades included
    (so it can be compared without re-running). `result` is deferred: listing never loads it.
    `symbol` is plain text, not a foreign key, so a saved run outlives a deleted practice stock."""

    __tablename__ = "saved_backtests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    symbol: Mapped[str] = mapped_column(String(10))
    type_label: Mapped[str] = mapped_column(String(60))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    initial_capital: Mapped[float] = mapped_column(Float)
    final_capital: Mapped[float] = mapped_column(Float)
    total_return_pct: Mapped[float] = mapped_column(Float)
    total_trades: Mapped[int] = mapped_column(Integer)
    win_rate_pct: Mapped[float] = mapped_column(Float)
    max_drawdown_pct: Mapped[float] = mapped_column(Float)
    risk_managed: Mapped[bool] = mapped_column(Boolean, default=False)
    costs_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    request: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = deferred(mapped_column(JSON))
