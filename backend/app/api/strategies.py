from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Signal, Strategy
from ..schemas import SignalOut, StrategyCreate, StrategyOut, StrategyUpdate
from ..services import strategy_service

router = APIRouter()


def _strategy_out(db: Session, strategy: Strategy) -> StrategyOut:
    signals = db.query(Signal).filter(Signal.strategy_id == strategy.id).all()
    return StrategyOut(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        type=strategy.type,
        symbol=strategy.stock.symbol,
        fast=strategy.parameters["fast"],
        slow=strategy.parameters["slow"],
        quantity=strategy.parameters["quantity"],
        auto_trade=strategy.auto_trade,
        created_at=strategy.created_at,
        signal_count=len(signals),
        buy_count=sum(1 for s in signals if s.signal == "BUY"),
        sell_count=sum(1 for s in signals if s.signal == "SELL"),
        held=strategy_service.strategy_held(db, strategy.id),
    )


def _signal_out(signal: Signal) -> SignalOut:
    return SignalOut(
        id=signal.id,
        strategy_id=signal.strategy_id,
        strategy_name=signal.strategy.name,
        symbol=signal.stock.symbol,
        date=signal.market_date,
        signal=signal.signal,
        price=signal.price,
        reason=signal.reason,
        details=signal.details,
        executed=signal.executed,
        note=signal.note,
        trade_quantity=signal.trade.quantity if signal.trade else None,
        trade_price=signal.trade.price if signal.trade else None,
        realized_pnl=signal.trade.realized_pnl if signal.trade else None,
    )


@router.get("/strategies", response_model=list[StrategyOut])
def list_strategies(db: Session = Depends(get_db)):
    strategies = db.query(Strategy).order_by(Strategy.id).all()
    return [_strategy_out(db, s) for s in strategies]


@router.post("/strategies", response_model=StrategyOut)
def create_strategy(body: StrategyCreate, db: Session = Depends(get_db)):
    strategy = strategy_service.create_strategy(
        db, body.symbol, body.fast, body.slow, body.quantity, body.auto_trade, body.name
    )
    return _strategy_out(db, strategy)


@router.patch("/strategies/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, body: StrategyUpdate, db: Session = Depends(get_db)):
    strategy = strategy_service.update_strategy(
        db, strategy_id, body.fast, body.slow, body.quantity, body.auto_trade, body.name
    )
    return _strategy_out(db, strategy)


@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    strategy_service.delete_strategy(db, strategy_id)
    return {"status": "deleted"}


@router.post("/strategies/{strategy_id}/run", response_model=list[SignalOut])
def run_strategy(strategy_id: int, db: Session = Depends(get_db)):
    strategy = strategy_service.get_strategy(db, strategy_id)
    return [_signal_out(s) for s in strategy_service.run_on_history(db, strategy)]


@router.get("/signals", response_model=list[SignalOut])
def list_signals(
    strategy_id: int | None = None,
    symbol: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return [_signal_out(s) for s in strategy_service.list_signals(db, strategy_id, symbol, limit)]
