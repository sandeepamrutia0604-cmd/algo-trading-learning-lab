from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import (
    EquityPoint,
    PortfolioBacktestRequest,
    PortfolioResultOut,
    PortfolioStockOut,
    PortfolioTradeOut,
    SavedPortfolioBacktestDetailOut,
    SavedPortfolioBacktestOut,
    SavePortfolioBacktestRequest,
    SkippedByReasonOut,
)
from ..services import portfolio_backtest_service, saved_portfolio_backtests
from ..services.saved_portfolio_backtests import SavedPortfolioNotFoundError

router = APIRouter()


def _run(body: PortfolioBacktestRequest, db: Session) -> PortfolioResultOut:
    run = portfolio_backtest_service.run(
        db, body.symbols, body.type, body.params, body.quantity, body.initial_capital, body.rules,
        start_date=body.start_date, end_date=body.end_date, fill_mode=body.fill_mode,
        stop_loss_pct=body.stop_loss_pct, take_profit_pct=body.take_profit_pct,
        risk_free_pct=body.risk_free_pct, benchmark=body.benchmark,
    )
    r = run.result
    point = lambda p: EquityPoint(date=p.date, value=round(p.value, 2))  # noqa: E731
    return PortfolioResultOut(
        symbols=run.symbols,
        type=run.defn.key,
        type_label=run.defn.label,
        params=run.params,
        rule=run.defn.rule_text(run.params),
        quantity=body.quantity,
        initial_capital=r.initial_capital,
        final_capital=r.final_capital,
        period_start=r.equity_curve[0].date,
        period_end=r.equity_curve[-1].date,
        total_return_pct=r.total_return_pct,
        total_trades=r.total_trades,
        winning_trades=r.winning_trades,
        losing_trades=r.losing_trades,
        win_rate_pct=r.win_rate_pct,
        max_drawdown_pct=r.max_drawdown_pct,
        skipped_buys=r.skipped_buys,
        skipped_by_reason=SkippedByReasonOut(**r.skipped_by_reason),
        stopped_out=r.stopped_out,
        take_profits=r.take_profits,
        stop_loss_pct=r.stop_loss_pct,
        take_profit_pct=r.take_profit_pct,
        fill_mode=r.fill_mode,
        unfilled_signals=r.unfilled_signals,
        peak_positions=r.peak_positions,
        max_open_positions=run.max_open_positions,
        metrics=run.metrics,
        risk_managed=run.risk_enabled,
        costs_applied=r.costs_applied,
        total_fees=round(r.total_fees, 2),
        slippage_cost=round(r.slippage_cost, 2),
        equity_curve=[point(p) for p in r.equity_curve],
        baseline_curve=[EquityPoint(date=d, value=round(v, 2)) for d, v in zip(run.days, run.baseline)],
        per_stock=[PortfolioStockOut(**vars(s)) for s in run.per_stock],
        trades=[
            PortfolioTradeOut(
                symbol=t.symbol, entry_date=t.entry_date, entry_price=t.entry_price, quantity=t.quantity,
                exit_date=t.exit_date, exit_price=t.exit_price, pnl=t.pnl, pnl_pct=t.pnl_pct, open=t.is_open,
                stopped_out=t.stopped_out, exit_reason=t.exit_reason, stop_pct=t.stop_pct,
            )
            for t in r.trades
        ],
    )


@router.post("/portfolio-backtests/run", response_model=PortfolioResultOut)
def run_portfolio_backtest(body: PortfolioBacktestRequest, db: Session = Depends(get_db)):
    """Trade one strategy across several stocks from one account (see engine/portfolio_backtest.py). Stores nothing."""
    return _run(body, db)


def _not_found(err: SavedPortfolioNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(err))


@router.get("/portfolio-backtests/saved", response_model=list[SavedPortfolioBacktestOut])
def list_saved(db: Session = Depends(get_db)):
    return saved_portfolio_backtests.list_all(db)


@router.post("/portfolio-backtests/saved", response_model=SavedPortfolioBacktestOut)
def save_portfolio_backtest(body: SavePortfolioBacktestRequest, db: Session = Depends(get_db)):
    """Run `body.request` again and keep it, so what is stored is what the server computed."""
    return saved_portfolio_backtests.save(db, body.name, body.request, _run(body.request, db))


@router.get("/portfolio-backtests/saved/{saved_id}", response_model=SavedPortfolioBacktestDetailOut)
def get_saved(saved_id: int, db: Session = Depends(get_db)):
    try:
        row = saved_portfolio_backtests.get(db, saved_id)
    except SavedPortfolioNotFoundError as err:
        raise _not_found(err) from None
    return SavedPortfolioBacktestDetailOut.model_validate(
        {**{c: getattr(row, c) for c in SavedPortfolioBacktestOut.model_fields}, "request": row.request, "result": row.result}
    )


@router.delete("/portfolio-backtests/saved/{saved_id}")
def delete_saved(saved_id: int, db: Session = Depends(get_db)):
    try:
        saved_portfolio_backtests.delete(db, saved_id)
    except SavedPortfolioNotFoundError as err:
        raise _not_found(err) from None
    return {"deleted": saved_id}
