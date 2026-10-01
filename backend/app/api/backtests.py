from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import (
    BacktestRequest,
    BacktestResultOut,
    BacktestTradeOut,
    EquityPoint,
    IndicatorPoint,
    SeriesOut,
)
from ..services import backtest_service

router = APIRouter()


@router.post("/backtests/run", response_model=BacktestResultOut)
def run_backtest(body: BacktestRequest, db: Session = Depends(get_db)):
    defn, params, dates, closes, result, risk_managed = backtest_service.run(
        db, body.symbol, body.type, body.params, body.quantity, body.initial_capital, body.rules
    )
    return BacktestResultOut(
        symbol=body.symbol.upper(),
        type=defn.key,
        type_label=defn.label,
        params=params,
        rule=defn.rule_text(params),
        quantity=body.quantity,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        win_rate_pct=result.win_rate_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        skipped_buys=result.skipped_buys,
        stopped_out=result.stopped_out,
        risk_managed=risk_managed,
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
                points=[IndicatorPoint(date=d, value=round(v, 4)) for d, v in zip(dates, s.values) if v is not None],
            )
            for s in defn.chart_series(closes, params)
        ],
    )
