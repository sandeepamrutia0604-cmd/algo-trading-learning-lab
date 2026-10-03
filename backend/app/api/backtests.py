from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import (
    BacktestRequest,
    BacktestResultOut,
    BacktestTradeOut,
    EquityPoint,
    IndicatorPoint,
    MonteCarloOut,
    MonteCarloRequest,
    OptimiseOut,
    OptimiseRequest,
    SaveBacktestRequest,
    SavedBacktestDetailOut,
    SavedBacktestOut,
    SeriesOut,
    WalkForwardOut,
    WalkForwardRequest,
)
from ..services import backtest_service, monte_carlo_service, optimizer_service, saved_backtests
from ..services.optimizer_service import AxisRequest
from ..services.saved_backtests import SavedBacktestNotFoundError

router = APIRouter()


def _run(body: BacktestRequest, db: Session) -> BacktestResultOut:
    defn, params, dates, closes, result, risk_managed = backtest_service.run(
        db, body.symbol, body.type, body.params, body.quantity, body.initial_capital, body.rules,
        start_date=body.start_date, end_date=body.end_date,
    )
    period_start, period_end = result.equity_curve[0].date, result.equity_curve[-1].date
    return BacktestResultOut(
        symbol=body.symbol.upper(),
        type=defn.key,
        type_label=defn.label,
        params=params,
        rule=defn.rule_text(params),
        quantity=body.quantity,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        period_start=period_start,
        period_end=period_end,
        total_return_pct=result.total_return_pct,
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        win_rate_pct=result.win_rate_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        skipped_buys=result.skipped_buys,
        stopped_out=result.stopped_out,
        risk_managed=risk_managed,
        costs_applied=result.costs_applied,
        total_fees=round(result.total_fees, 2),
        slippage_cost=round(result.slippage_cost, 2),
        equity_curve=[EquityPoint(date=p.date, value=round(p.value, 2)) for p in result.equity_curve],
        trades=[
            BacktestTradeOut(
                entry_date=t.entry_date,
                entry_price=t.entry_price,
                quantity=t.quantity,
                exit_date=t.exit_date,
                exit_price=t.exit_price,
                pnl=t.pnl,
                pnl_pct=t.pnl_pct,
                open=t.is_open,
                stopped_out=t.stopped_out,
            )
            for t in result.trades
        ],
        series=[
            SeriesOut(
                name=s.name,
                panel=s.panel,
                color=s.color,
                dash=s.dash,
                width=s.width,
                fill_to_previous=s.fill_to_previous,
                y_range=list(s.y_range) if s.y_range else None,
                points=[IndicatorPoint(date=d, value=round(v, 4)) for d, v in zip(dates, s.values) if v is not None and d >= period_start],
            )
            for s in defn.chart_series(closes, params)
        ],
    )


@router.post("/backtests/run", response_model=BacktestResultOut)
def run_backtest(body: BacktestRequest, db: Session = Depends(get_db)):
    return _run(body, db)


@router.post("/backtests/optimise", response_model=OptimiseOut)
def optimise(body: OptimiseRequest, db: Session = Depends(get_db)):
    """Try every combination of one or two settings on a training period, then see how the winner
    does on an unseen test period (see services/optimizer_service.py). Stores nothing."""
    axis = lambda a: AxisRequest(a.param, a.low, a.high, a.step)  # noqa: E731
    return optimizer_service.optimise(
        db,
        body.symbol,
        body.type,
        body.params,
        axis(body.x),
        axis(body.y) if body.y else None,
        body.quantity,
        body.initial_capital,
        body.metric,
        body.train_start,
        body.train_end,
        body.test_start,
        body.test_end,
    )


@router.post("/backtests/monte-carlo", response_model=MonteCarloOut)
def monte_carlo(body: MonteCarloRequest, db: Session = Depends(get_db)):
    """Run the backtest, then re-play its closed trades many times in other orders (or resampled)
    to show how much of the result was luck (see engine/monte_carlo.py). Stores nothing."""
    return monte_carlo_service.analyse(db, body.request, body.simulations, body.method, body.seed)


@router.post("/backtests/walk-forward", response_model=WalkForwardOut)
def walk_forward(body: WalkForwardRequest, db: Session = Depends(get_db)):
    """Optimise on a window, trade the winner on the window after it, and slide forward; the test
    windows are chained into one out-of-sample record (see services/optimizer_service.py)."""
    axis = lambda a: AxisRequest(a.param, a.low, a.high, a.step)  # noqa: E731
    return optimizer_service.walk_forward(
        db,
        body.symbol,
        body.type,
        body.params,
        axis(body.x),
        axis(body.y) if body.y else None,
        body.quantity,
        body.initial_capital,
        body.metric,
        body.folds,
        body.train_ratio,
        body.mode,
        body.start_date,
        body.end_date,
    )


# ---------- saved backtests ----------


def _not_found(err: SavedBacktestNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(err))


@router.get("/backtests/saved", response_model=list[SavedBacktestOut])
def list_saved(db: Session = Depends(get_db)):
    return saved_backtests.list_all(db)


@router.post("/backtests/saved", response_model=SavedBacktestOut)
def save_backtest(body: SaveBacktestRequest, db: Session = Depends(get_db)):
    """Run `body.request` again and keep it, so what is stored is what the server computed."""
    return saved_backtests.save(db, body.name, body.request, _run(body.request, db))


@router.get("/backtests/saved/{saved_id}", response_model=SavedBacktestDetailOut)
def get_saved(saved_id: int, db: Session = Depends(get_db)):
    try:
        row = saved_backtests.get(db, saved_id)
    except SavedBacktestNotFoundError as err:
        raise _not_found(err) from None
    return SavedBacktestDetailOut.model_validate({**{c: getattr(row, c) for c in SavedBacktestOut.model_fields}, "request": row.request, "result": row.result})


@router.delete("/backtests/saved/{saved_id}")
def delete_saved(saved_id: int, db: Session = Depends(get_db)):
    try:
        saved_backtests.delete(db, saved_id)
    except SavedBacktestNotFoundError as err:
        raise _not_found(err) from None
    return {"deleted": saved_id}
