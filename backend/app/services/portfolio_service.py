from sqlalchemy.orm import Session

from ..models import Position
from ..models.portfolio import INITIAL_VIRTUAL_CASH
from .trading_service import get_portfolio


def get_portfolio_summary(db: Session) -> dict:
    portfolio = get_portfolio(db)
    positions = db.query(Position).all()

    invested = sum(p.quantity * p.average_price for p in positions)
    market_value = sum(p.quantity * p.stock.current_price for p in positions)
    unrealized_pnl = market_value - invested
    portfolio_value = portfolio.virtual_cash + market_value
    total_pnl = portfolio_value - INITIAL_VIRTUAL_CASH

    return {
        "cash": portfolio.virtual_cash,
        "invested": invested,
        "market_value": market_value,
        "portfolio_value": portfolio_value,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": portfolio.realized_pnl,
        "total_pnl": total_pnl,
        "return_pct": (total_pnl / INITIAL_VIRTUAL_CASH) * 100,
    }


def get_positions_with_pnl(db: Session) -> list[dict]:
    positions = db.query(Position).all()
    result = []
    for p in positions:
        market_value = p.quantity * p.stock.current_price
        cost_basis = p.quantity * p.average_price
        result.append(
            {
                "symbol": p.stock.symbol,
                "name": p.stock.name,
                "quantity": p.quantity,
                "average_price": p.average_price,
                "current_price": p.stock.current_price,
                "market_value": market_value,
                "unrealized_pnl": market_value - cost_basis,
            }
        )
    return result
