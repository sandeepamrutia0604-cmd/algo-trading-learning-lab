from datetime import date

from sqlalchemy.orm import Session

from ..models import Position, PriceData, Signal, Stock, Strategy, Trade
from ..strategies.ma_crossover import MAX_PERIOD, MIN_PERIOD, CrossoverSignal, ma_crossover_signals
from . import market_service, trading_service
from .exceptions import InvalidStrategyError, StockNotFoundError, StrategyNotFoundError, TradingError

STRATEGY_TYPE = "ma_crossover"


def rule_text(fast: int, slow: int) -> str:
    return f"BUY when the {fast}-day average crosses above the {slow}-day average; SELL when it crosses below."


def default_name(symbol: str, fast: int, slow: int) -> str:
    return f"MA Crossover {fast}/{slow} on {symbol}"


def _validate(fast: int, slow: int, quantity: int) -> None:
    if not (MIN_PERIOD <= fast < slow <= MAX_PERIOD):
        raise InvalidStrategyError(f"Periods must satisfy {MIN_PERIOD} <= fast < slow <= {MAX_PERIOD}")
    if quantity < 1:
        raise InvalidStrategyError("Quantity must be at least 1")


def _get_stock(db: Session, symbol: str) -> Stock:
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if stock is None:
        raise StockNotFoundError(f"Unknown stock symbol: {symbol}")
    return stock


def get_strategy(db: Session, strategy_id: int) -> Strategy:
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        raise StrategyNotFoundError(f"Strategy {strategy_id} not found")
    return strategy


def create_strategy(
    db: Session,
    symbol: str,
    fast: int,
    slow: int,
    quantity: int,
    auto_trade: bool = False,
    name: str | None = None,
) -> Strategy:
    _validate(fast, slow, quantity)
    stock = _get_stock(db, symbol)
    strategy = Strategy(
        name=name or default_name(stock.symbol, fast, slow),
        description=rule_text(fast, slow),
        type=STRATEGY_TYPE,
        stock_id=stock.id,
        parameters={"fast": fast, "slow": slow, "quantity": quantity},
        auto_trade=auto_trade,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def update_strategy(
    db: Session,
    strategy_id: int,
    fast: int | None = None,
    slow: int | None = None,
    quantity: int | None = None,
    auto_trade: bool | None = None,
    name: str | None = None,
) -> Strategy:
    strategy = get_strategy(db, strategy_id)
    params = dict(strategy.parameters)
    params["fast"] = fast if fast is not None else params["fast"]
    params["slow"] = slow if slow is not None else params["slow"]
    params["quantity"] = quantity if quantity is not None else params["quantity"]
    _validate(params["fast"], params["slow"], params["quantity"])

    if params != strategy.parameters:
        strategy.parameters = params
        strategy.description = rule_text(params["fast"], params["slow"])
    if auto_trade is not None:
        strategy.auto_trade = auto_trade
    if name:
        strategy.name = name
    db.commit()
    db.refresh(strategy)
    return strategy


def delete_strategy(db: Session, strategy_id: int) -> None:
    strategy = get_strategy(db, strategy_id)
    db.query(Trade).filter(Trade.strategy_id == strategy.id).update({Trade.strategy_id: None})
    db.query(Signal).filter(Signal.strategy_id == strategy.id).delete()
    db.delete(strategy)
    db.commit()


def _series(db: Session, stock_id: int) -> tuple[list[date], list[float]]:
    rows = (
        db.query(PriceData.timestamp, PriceData.close)
        .filter(PriceData.stock_id == stock_id)
        .order_by(PriceData.timestamp)
        .all()
    )
    return [r[0].date() for r in rows], [r[1] for r in rows]


def build_reason(side: str, fast: int, slow: int, sig: CrossoverSignal) -> str:
    if side == "BUY":
        return (
            f"The {fast}-day average (₹{sig.fast_ma:.2f}) crossed above the {slow}-day average "
            f"(₹{sig.slow_ma:.2f}). The day before it was at or below it "
            f"(₹{sig.prev_fast_ma:.2f} vs ₹{sig.prev_slow_ma:.2f})."
        )
    return (
        f"The {fast}-day average (₹{sig.fast_ma:.2f}) crossed below the {slow}-day average "
        f"(₹{sig.slow_ma:.2f}). The day before it was at or above it "
        f"(₹{sig.prev_fast_ma:.2f} vs ₹{sig.prev_slow_ma:.2f})."
    )


def _make_signal(strategy: Strategy, day: date, price: float, sig: CrossoverSignal) -> Signal:
    fast, slow = strategy.parameters["fast"], strategy.parameters["slow"]
    return Signal(
        strategy_id=strategy.id,
        stock_id=strategy.stock_id,
        market_date=day,
        signal=sig.side,
        price=price,
        reason=build_reason(sig.side, fast, slow, sig),
        details={
            "rule": rule_text(fast, slow),
            "fast_period": fast,
            "slow_period": slow,
            "fast_ma": round(sig.fast_ma, 4),
            "slow_ma": round(sig.slow_ma, 4),
            "prev_fast_ma": round(sig.prev_fast_ma, 4),
            "prev_slow_ma": round(sig.prev_slow_ma, 4),
            "quantity": strategy.parameters["quantity"],
        },
        executed=False,
        note="Historical signal: no trade placed",
    )


def run_on_history(db: Session, strategy: Strategy) -> list[Signal]:
    """Mark every crossover in the current price history. Places no trades; keeps executed signals."""
    fast, slow = strategy.parameters["fast"], strategy.parameters["slow"]
    dates, closes = _series(db, strategy.stock_id)
    computed = {dates[s.index]: s for s in ma_crossover_signals(closes, fast, slow)}
    existing = {s.market_date: s for s in db.query(Signal).filter(Signal.strategy_id == strategy.id).all()}

    for day, old in list(existing.items()):
        if not old.executed and (day not in computed or computed[day].side != old.signal):
            db.delete(old)
            del existing[day]
    db.flush()

    price_on = dict(zip(dates, closes))
    for day, sig in computed.items():
        if day not in existing:
            db.add(_make_signal(strategy, day, price_on[day], sig))
    db.commit()
    return list_signals(db, strategy_id=strategy.id)


def strategy_held(db: Session, strategy_id: int) -> int:
    trades = db.query(Trade).filter(Trade.strategy_id == strategy_id).all()
    return sum(t.quantity if t.side == "BUY" else -t.quantity for t in trades)


def _execute_signal(db: Session, strategy: Strategy, stock: Stock, signal: Signal) -> Trade:
    quantity = strategy.parameters["quantity"]
    reason = f"{strategy.name}: {signal.signal} signal"[:200]
    if signal.signal == "BUY":
        return trading_service.execute_buy(db, stock.symbol, quantity, reason=reason, strategy_id=strategy.id)

    position = db.query(Position).filter(Position.stock_id == stock.id).first()
    sell_qty = min(strategy_held(db, strategy.id), position.quantity if position else 0)
    if sell_qty <= 0:
        raise TradingError("this strategy holds no shares to sell")
    return trading_service.execute_sell(db, stock.symbol, sell_qty, reason=reason, strategy_id=strategy.id)


def run_auto_strategies(db: Session) -> list[str]:
    """Check each auto-trade strategy for a crossover on its stock's latest day and trade it."""
    events: list[str] = []
    for strategy in db.query(Strategy).filter(Strategy.auto_trade.is_(True)).all():
        dates, closes = _series(db, strategy.stock_id)
        if not closes:
            continue
        fast, slow = strategy.parameters["fast"], strategy.parameters["slow"]
        latest = [s for s in ma_crossover_signals(closes, fast, slow) if s.index == len(closes) - 1]
        if not latest:
            continue
        day = dates[-1]
        already = db.query(Signal).filter(Signal.strategy_id == strategy.id, Signal.market_date == day).first()
        if already is not None:
            continue

        stock = db.get(Stock, strategy.stock_id)
        signal = _make_signal(strategy, day, closes[-1], latest[0])
        db.add(signal)
        db.flush()
        try:
            trade = _execute_signal(db, strategy, stock, signal)
            signal.executed = True
            signal.trade_id = trade.id
            signal.note = None
            events.append(f"{strategy.name}: {trade.side} {trade.quantity} {stock.symbol} @ ₹{trade.price:,.2f}")
        except TradingError as exc:
            signal.executed = False
            signal.note = f"Skipped: {exc}"[:300]
            events.append(f"{strategy.name}: {signal.signal} signal skipped ({exc})")
        db.commit()
    return events


def advance_market(db: Session, days: int) -> list[str]:
    """Advance the market; with auto-trade strategies enabled, go day by day so each signal trades at its own close."""
    if not db.query(Strategy).filter(Strategy.auto_trade.is_(True)).count():
        market_service.advance(db, days)
        return []
    events: list[str] = []
    for _ in range(days):
        market_service.advance(db, 1)
        events.extend(run_auto_strategies(db))
    return events


def list_signals(
    db: Session, strategy_id: int | None = None, symbol: str | None = None, limit: int | None = None
) -> list[Signal]:
    query = db.query(Signal)
    if strategy_id is not None:
        query = query.filter(Signal.strategy_id == strategy_id)
    if symbol:
        stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
        if stock is None:
            raise StockNotFoundError(f"Unknown stock symbol: {symbol}")
        query = query.filter(Signal.stock_id == stock.id)
    query = query.order_by(Signal.market_date.desc(), Signal.id.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def clear_unexecuted_signals(db: Session) -> None:
    db.query(Signal).filter(Signal.executed.is_(False)).delete()
    db.commit()


def clear_all_signals(db: Session) -> None:
    db.query(Signal).delete()
    db.commit()
