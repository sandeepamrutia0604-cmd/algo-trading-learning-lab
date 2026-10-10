"""Keeping portfolio backtests you want to look at again. Like saved_backtests.py: saving re-runs the request on
the server and stores both request and result, so a saved row is always something the server really computed."""

from sqlalchemy.orm import Session

from ..models import SavedPortfolioBacktest
from ..schemas import PortfolioBacktestRequest, PortfolioResultOut
from .exceptions import TradingError

MAX_SAVED = 200


class SavedPortfolioNotFoundError(TradingError):
    pass


def default_name(result: PortfolioResultOut) -> str:
    shown = ", ".join(result.symbols[:4]) + (f" +{len(result.symbols) - 4}" if len(result.symbols) > 4 else "")
    name = f"{result.type_label} on {len(result.symbols)} stocks ({shown})"
    if result.fill_mode == "next_open":
        name += ", next-open fills"
    return name


def save(db: Session, name: str | None, request: PortfolioBacktestRequest, result: PortfolioResultOut) -> SavedPortfolioBacktest:
    if db.query(SavedPortfolioBacktest).count() >= MAX_SAVED:
        raise TradingError(f"You can keep up to {MAX_SAVED} saved portfolio backtests. Delete some you no longer need first.")
    row = SavedPortfolioBacktest(
        name=(name or "").strip() or default_name(result),
        symbols=result.symbols,
        type_label=result.type_label,
        period_start=result.period_start,
        period_end=result.period_end,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        total_trades=result.total_trades,
        win_rate_pct=result.win_rate_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        request=request.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_all(db: Session) -> list[SavedPortfolioBacktest]:
    return db.query(SavedPortfolioBacktest).order_by(SavedPortfolioBacktest.created_at.desc(), SavedPortfolioBacktest.id.desc()).all()


def get(db: Session, saved_id: int) -> SavedPortfolioBacktest:
    row = db.get(SavedPortfolioBacktest, saved_id)
    if row is None:
        raise SavedPortfolioNotFoundError(f"Saved portfolio backtest {saved_id} doesn't exist (it may have been deleted)")
    return row


def delete(db: Session, saved_id: int) -> None:
    db.delete(get(db, saved_id))
    db.commit()
