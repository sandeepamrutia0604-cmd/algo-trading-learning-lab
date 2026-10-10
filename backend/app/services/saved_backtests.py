"""Keeping backtests you want to look at again. Saving re-runs the request on the server and
stores both the request and the result (see models/saved_backtest.py), so a saved row is always
something the server really computed, never a payload a page made up."""

from sqlalchemy.orm import Session

from ..models import SavedBacktest
from ..schemas import BacktestRequest, BacktestResultOut
from .exceptions import TradingError

MAX_SAVED = 200


class SavedBacktestNotFoundError(TradingError):
    pass


def default_name(result: BacktestResultOut, request: BacktestRequest) -> str:
    name = f"{result.type_label} on {result.symbol}"
    if request.start_date or request.end_date:
        name += f" ({result.period_start} to {result.period_end})"
    if result.fill_mode == "next_open":
        name += ", next-open fills"
    if result.stop_loss_pct or result.take_profit_pct:
        levels = [f"{result.stop_loss_pct:g}% stop" if result.stop_loss_pct else "", f"{result.take_profit_pct:g}% target" if result.take_profit_pct else ""]
        name += ", " + " / ".join(level for level in levels if level)
    return name


def save(db: Session, name: str | None, request: BacktestRequest, result: BacktestResultOut) -> SavedBacktest:
    if db.query(SavedBacktest).count() >= MAX_SAVED:
        raise TradingError(f"You can keep up to {MAX_SAVED} saved backtests. Delete some you no longer need first.")
    row = SavedBacktest(
        name=(name or "").strip() or default_name(result, request),
        symbol=result.symbol,
        type_label=result.type_label,
        period_start=result.period_start,
        period_end=result.period_end,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        total_trades=result.total_trades,
        win_rate_pct=result.win_rate_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        risk_managed=result.risk_managed,
        costs_applied=result.costs_applied,
        request=request.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_all(db: Session) -> list[SavedBacktest]:
    return db.query(SavedBacktest).order_by(SavedBacktest.created_at.desc(), SavedBacktest.id.desc()).all()


def get(db: Session, saved_id: int) -> SavedBacktest:
    row = db.get(SavedBacktest, saved_id)
    if row is None:
        raise SavedBacktestNotFoundError(f"Saved backtest {saved_id} doesn't exist (it may have been deleted)")
    return row


def delete(db: Session, saved_id: int) -> None:
    db.delete(get(db, saved_id))
    db.commit()
