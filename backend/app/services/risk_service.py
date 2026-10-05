from sqlalchemy.orm import Session

from ..engine import risk_math
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


def entry_stop_pct(db: Session, closes: list[float]) -> float | None:
    """The stop distance (percent below the entry) for a position about to be opened on the last
    close in `closes`: the fixed stop-loss %, or in volatility mode a multiple of the stock's
    recent daily volatility. None when risk management is off."""
    settings = get_settings(db)
    if not settings.enabled:
        return None
    return risk_math.entry_stop_pct(
        closes, settings.stop_mode or "fixed", settings.volatility_window or 20, settings.volatility_multiplier or 2.0, settings.stop_loss_pct
    )


def position_size(
    db: Session, price: float, fallback_qty: int, *, fit_allocation_cap: bool = False, stop_pct: float | None = None
) -> int:
    """Risk-based share count for a BUY: (capital * max risk %) / (price * stop-loss %),
    the sizing formula from the plan's example. Falls back to `fallback_qty` (the strategy's
    own configured quantity) when risk management is off or isn't fully configured.
    `stop_pct` is the stop distance for this particular trade (see entry_stop_pct); without it
    the fixed stop-loss setting is used.
    `fit_allocation_cap` shrinks the result to the max-allocation-per-stock limit (as the
    backtest engine does) instead of leaving a larger buy to be rejected by the cap."""
    settings = get_settings(db)
    if not settings.enabled:
        return fallback_qty
    return risk_math.position_size(
        portfolio_value(db),
        price,
        settings.max_risk_per_trade_pct,
        stop_pct if stop_pct is not None else settings.stop_loss_pct,
        fallback_qty,
        settings.max_allocation_pct if fit_allocation_cap else 0.0,
    )


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
    """The exit price for a strategy's current open position, based on its entry trade and the
    stop distance that trade was opened with (a volatility-based stop is fixed at entry), or else
    the configured stop-loss %. None if risk management or the stop-loss isn't configured."""
    settings = get_settings(db)
    if not settings.enabled:
        return None
    entry = (
        db.query(Trade)
        .filter(Trade.strategy_id == strategy_id, Trade.side == "BUY")
        .order_by(Trade.id.desc())
        .first()
    )
    if entry is None:
        return None
    stop_pct = entry.stop_pct if entry.stop_pct is not None else settings.stop_loss_pct
    if not stop_pct:
        return None
    return risk_math.stop_loss_price(entry.price, stop_pct)
