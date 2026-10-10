from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, deferred, mapped_column

from ..db import Base


class SavedPortfolioBacktest(Base):
    """A portfolio backtest you chose to keep: the same idea as SavedBacktest (headline numbers in columns, the
    exact `request` so it can be loaded back and re-run, the full `result` deferred so listing stays cheap), kept
    in its own table because its request names several stocks. `symbols` is plain text, not foreign keys."""

    __tablename__ = "saved_portfolio_backtests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    symbols: Mapped[list] = mapped_column(JSON)
    type_label: Mapped[str] = mapped_column(String(60))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    initial_capital: Mapped[float] = mapped_column(Float)
    final_capital: Mapped[float] = mapped_column(Float)
    total_return_pct: Mapped[float] = mapped_column(Float)
    total_trades: Mapped[int] = mapped_column(Integer)
    win_rate_pct: Mapped[float] = mapped_column(Float)
    max_drawdown_pct: Mapped[float] = mapped_column(Float)
    request: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = deferred(mapped_column(JSON))
