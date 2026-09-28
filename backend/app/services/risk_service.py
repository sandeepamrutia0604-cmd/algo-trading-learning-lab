from sqlalchemy.orm import Session

from ..models import Portfolio, Position, RiskSettings, Stock, Trade
from .exceptions import TradingError


def get_settings(db: Session) -> RiskSettings:
    settings = db.query(RiskSettings).first()
    if settings is None:
        raise RuntimeError("RiskSettings not seeded — call ensure_seed_data() at startup")
    return settings


def update_settings(db: Session, **fields) -> RiskSettings:
    settings = get_settings(db)
    for key, value in fields.items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings


def portfolio_value(db: Session) -> float:
    portfolio = db.query(Portfolio).first()
    market_value = sum(p.quantity * p.stock.current_price for p in db.query(Position).all())
    return portfolio.virtual_cash + market_value


def position_size(db: Session, price: float, fallback_qty: int) -> int:
    """Risk-based share count for a BUY: (capital * max risk %) / (price * stop-loss %),
    the sizing formula from the plan's example. Falls back to `fallback_qty` (the strategy's
    own configured quantity) when risk management is off or isn't fully configured."""
    settings = get_settings(db)
    if not settings.enabled or not settings.max_risk_per_trade_pct or not settings.stop_loss_pct:
        return fallback_qty
    risk_amount = portfolio_value(db) * settings.max_risk_per_trade_pct / 100
    risk_per_share = price * settings.stop_loss_pct / 100
    if risk_per_share <= 0:
        return fallback_qty
    return max(0, int(risk_amount // risk_per_share))


def check_buy_allowed(db: Session, stock: Stock, quantity: int, price: float) -> None:
    """Raise TradingError if this BUY would breach the max-open-positions or
    max-allocation-per-stock caps. Applies to every BUY, manual or strategy-placed."""
    settings = get_settings(db)
    if not settings.enabled:
        return

    existing = db.query(Position).filter(Position.stock_id == stock.id).first()

    if settings.max_open_positions and existing is None:
        open_count = db.query(Position).count()
        if open_count >= settings.max_open_positions:
            raise TradingError(
                f"Risk limit: already holding the maximum {settings.max_open_positions} open positions"
            )

    if settings.max_allocation_pct:
        value = portfolio_value(db)
        if value > 0:
            existing_value = existing.quantity * price if existing else 0.0
            allocation_pct = (existing_value + quantity * price) / value * 100
            if allocation_pct > settings.max_allocation_pct + 1e-9:
                raise TradingError(
                    f"Risk limit: buying would put {allocation_pct:.1f}% of the portfolio in "
                    f"{stock.symbol}, over the {settings.max_allocation_pct:g}% max allocation"
                )


def stop_loss_price_for_strategy(db: Session, strategy_id: int) -> float | None:
    """The exit price for a strategy's current open position, based on its entry trade and
    the configured stop-loss %. None if risk management or the stop-loss isn't configured."""
    settings = get_settings(db)
    if not settings.enabled or not settings.stop_loss_pct:
        return None
    entry = (
        db.query(Trade)
        .filter(Trade.strategy_id == strategy_id, Trade.side == "BUY")
        .order_by(Trade.id.desc())
        .first()
    )
    if entry is None:
        return None
    return entry.price * (1 - settings.stop_loss_pct / 100)
