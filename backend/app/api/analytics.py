from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Trade
from ..schemas import EquityPoint, MonthlyReturnOut, PerformanceOut, StrategyPerformanceOut, TradeStatsOut
from ..services import analytics_service, portfolio_service

router = APIRouter()


@router.get("/analytics/performance", response_model=PerformanceOut)
def performance(db: Session = Depends(get_db)):
    curve = portfolio_service.get_equity_curve(db)
    summary = portfolio_service.get_portfolio_summary(db)
    trades = db.query(Trade).filter(Trade.realized_pnl.isnot(None)).order_by(Trade.market_date).all()

    stats = analytics_service.trade_stats(trades)
    eq_metrics = analytics_service.equity_metrics(curve)

    return PerformanceOut(
        total_return_pct=summary["return_pct"],
        max_drawdown_pct=eq_metrics["max_drawdown_pct"],
        sharpe_ratio=eq_metrics["sharpe_ratio"],
        trade_stats=TradeStatsOut(**stats),
        equity_curve=[EquityPoint(**c) for c in curve],
        drawdown_curve=[EquityPoint(**c) for c in analytics_service.drawdown_curve(curve)],
        monthly_returns=[MonthlyReturnOut(**m) for m in analytics_service.monthly_returns(curve)],
        trade_pnls=[t.realized_pnl for t in trades],
        by_strategy=[StrategyPerformanceOut(**row) for row in analytics_service.strategy_comparison(db)],
    )
