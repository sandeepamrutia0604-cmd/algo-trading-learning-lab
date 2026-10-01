from datetime import date

from sqlalchemy.orm import Session

from ..adapters import get_market_data_adapter
from ..engine import rule_engine
from ..models import Position, Signal, Stock, Strategy, Trade
from ..strategies.base import ChartSeries, SignalEvent, StrategyDef
from ..strategies.registry import get_definition
from . import market_service, risk_service, trading_service
from .exceptions import InvalidStrategyError, StockNotFoundError, StrategyNotFoundError, TradingError

CUSTOM_TYPE = "custom"


def _definition(type_key: str) -> StrategyDef:
    try:
        return get_definition(type_key)
    except ValueError as exc:
        raise InvalidStrategyError(str(exc)) from exc


def _normalize(defn: StrategyDef, params: dict | None) -> dict:
    try:
        return defn.normalize(params)
    except ValueError as exc:
        raise InvalidStrategyError(str(exc)) from exc


def _validated_rules(rules: dict | None) -> dict:
    try:
        rule_engine.validate_rules(rules)
    except ValueError as exc:
        raise InvalidStrategyError(str(exc)) from exc
    return rules


def strategy_params(strategy: Strategy) -> dict:
    """The strategy's tuning parameters (everything except the order quantity)."""
    return {k: v for k, v in strategy.parameters.items() if k != "quantity"}


def strategy_quantity(strategy: Strategy) -> int:
    return strategy.parameters["quantity"]


def strategy_definition(strategy: Strategy) -> StrategyDef:
    if strategy.type == CUSTOM_TYPE:
        return rule_engine.build_definition(strategy.rules)
    return _definition(strategy.type)


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
    params: dict | None = None,
    quantity: int = 10,
    auto_trade: bool = False,
    name: str | None = None,
    type_key: str = "ma_crossover",
    rules: dict | None = None,
) -> Strategy:
    if quantity < 1:
        raise InvalidStrategyError("Quantity must be at least 1")
    stock = _get_stock(db, symbol)

    if type_key == CUSTOM_TYPE:
        clean_rules = _validated_rules(rules)
        defn = rule_engine.build_definition(clean_rules)
        strategy = Strategy(
            name=name or f"Custom strategy on {stock.symbol}",
            description=defn.rule_text({}),
            type=CUSTOM_TYPE,
            stock_id=stock.id,
            parameters={"quantity": quantity},
            rules=clean_rules,
            auto_trade=auto_trade,
        )
    else:
        defn = _definition(type_key)
        clean = _normalize(defn, params)
        strategy = Strategy(
            name=name or defn.default_name(clean, stock.symbol),
            description=defn.rule_text(clean),
            type=defn.key,
            stock_id=stock.id,
            parameters={**clean, "quantity": quantity},
            auto_trade=auto_trade,
        )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def update_strategy(
    db: Session,
    strategy_id: int,
    params: dict | None = None,
    quantity: int | None = None,
    auto_trade: bool | None = None,
    name: str | None = None,
    rules: dict | None = None,
) -> Strategy:
    strategy = get_strategy(db, strategy_id)
    new_quantity = quantity if quantity is not None else strategy_quantity(strategy)
    if new_quantity < 1:
        raise InvalidStrategyError("Quantity must be at least 1")

    if strategy.type == CUSTOM_TYPE:
        if rules is not None:
            clean_rules = _validated_rules(rules)
            strategy.rules = clean_rules
            strategy.description = rule_engine.build_definition(clean_rules).rule_text({})
        strategy.parameters = {"quantity": new_quantity}
    else:
        defn = strategy_definition(strategy)
        merged = {**strategy_params(strategy), **(params or {})}
        clean = _normalize(defn, merged)
        if clean != strategy_params(strategy):
            strategy.description = defn.rule_text(clean)
        strategy.parameters = {**clean, "quantity": new_quantity}

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


def _series(db: Session, symbol: str) -> tuple[list[date], list[float]]:
    """Historical closes for `symbol`, through the market data adapter (Phase 11) so the
    strategy engine never depends on how the candles were actually produced."""
    candles = get_market_data_adapter(db).get_historical_candles(symbol)
    return [c.date for c in candles], [c.close for c in candles]


def chart_series(db: Session, strategy: Strategy) -> tuple[list[date], list[ChartSeries]]:
    defn = strategy_definition(strategy)
    dates, closes = _series(db, strategy.stock.symbol)
    return dates, defn.chart_series(closes, strategy_params(strategy))


def _make_signal(strategy: Strategy, defn: StrategyDef, day: date, price: float, event: SignalEvent) -> Signal:
    return Signal(
        strategy_id=strategy.id,
        stock_id=strategy.stock_id,
        market_date=day,
        signal=event.side,
        price=price,
        reason="; ".join(event.checks)[:400],
        details={
            "rule": defn.rule_text(strategy_params(strategy)),
            "headline": event.headline,
            "checks": event.checks,
            "values": event.values,
            "quantity": strategy_quantity(strategy),
        },
        executed=False,
        note="Historical signal: no trade placed",
    )


def run_on_history(db: Session, strategy: Strategy) -> list[Signal]:
    """Mark every signal in the current price history. Places no trades; keeps executed signals."""
    defn = strategy_definition(strategy)
    dates, closes = _series(db, strategy.stock.symbol)
    computed = {dates[e.index]: e for e in defn.generate(closes, strategy_params(strategy))}
    existing = {s.market_date: s for s in db.query(Signal).filter(Signal.strategy_id == strategy.id).all()}

    for day, old in list(existing.items()):
        if not old.executed and (day not in computed or computed[day].side != old.signal):
            db.delete(old)
            del existing[day]
    db.flush()

    price_on = dict(zip(dates, closes))
    for day, event in computed.items():
        if day not in existing:
            db.add(_make_signal(strategy, defn, day, price_on[day], event))
    db.commit()
    return list_signals(db, strategy_id=strategy.id)


def strategy_held(db: Session, strategy_id: int) -> int:
    trades = db.query(Trade).filter(Trade.strategy_id == strategy_id).all()
    return sum(t.quantity if t.side == "BUY" else -t.quantity for t in trades)


def _execute_signal(db: Session, strategy: Strategy, stock: Stock, signal: Signal) -> Trade:
    reason = f"{strategy.name}: {signal.signal} signal"[:200]
    held = strategy_held(db, strategy.id)

    if signal.signal == "BUY":
        if held > 0:
            raise TradingError("this strategy is already holding shares")
        quantity = risk_service.position_size(db, stock.current_price, strategy_quantity(strategy))
        if quantity <= 0:
            raise TradingError("risk-based position sizing rounds down to zero shares at this price")
        return trading_service.execute_buy(db, stock.symbol, quantity, reason=reason, strategy_id=strategy.id)

    position = db.query(Position).filter(Position.stock_id == stock.id).first()
    sell_qty = min(held, position.quantity if position else 0)
    if sell_qty <= 0:
        raise TradingError("this strategy holds no shares to sell")
    return trading_service.execute_sell(db, stock.symbol, sell_qty, reason=reason, strategy_id=strategy.id)


def run_auto_strategies(db: Session) -> list[str]:
    """Check each auto-trade strategy for a signal on its stock's latest day and trade it.
    A held position is checked against its risk-management stop-loss first; that protective
    exit overrides the strategy's own signal for the day."""
    events: list[str] = []
    for strategy in db.query(Strategy).filter(Strategy.auto_trade.is_(True)).all():
        stock = strategy.stock
        dates, closes = _series(db, stock.symbol)
        if not closes:
            continue

        held = strategy_held(db, strategy.id)
        if held > 0:
            stop_price = risk_service.stop_loss_price_for_strategy(db, strategy.id)
            if stop_price is not None and closes[-1] <= stop_price:
                trade = trading_service.execute_sell(
                    db, stock.symbol, held, reason=f"{strategy.name}: stop-loss at ₹{stop_price:,.2f}", strategy_id=strategy.id
                )
                events.append(f"{strategy.name}: STOP-LOSS SELL {trade.quantity} {stock.symbol} @ ₹{trade.price:,.2f}")
                continue

        defn = strategy_definition(strategy)
        latest = [e for e in defn.generate(closes, strategy_params(strategy)) if e.index == len(closes) - 1]
        if not latest:
            continue
        day = dates[-1]
        already = db.query(Signal).filter(Signal.strategy_id == strategy.id, Signal.market_date == day).first()
        if already is not None:
            continue

        signal = _make_signal(strategy, defn, day, closes[-1], latest[0])
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
