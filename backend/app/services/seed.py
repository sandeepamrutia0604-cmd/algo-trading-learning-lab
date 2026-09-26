from sqlalchemy.orm import Session

from ..models import Portfolio, PriceData, Stock
from . import market_service

DUMMY_STOCKS = [
    {"symbol": "ALPHA", "name": "Alpha Industries", "starting_price": 100.0},
    {"symbol": "BETA", "name": "Beta Technologies", "starting_price": 250.0},
    {"symbol": "GAMMA", "name": "Gamma Foods", "starting_price": 75.0},
    {"symbol": "DELTA", "name": "Delta Motors", "starting_price": 500.0},
]


def ensure_seed_data(db: Session, with_history: bool = True) -> None:
    if db.query(Portfolio).first() is None:
        db.add(Portfolio())

    existing_symbols = {s.symbol for s in db.query(Stock).all()}
    for stock in DUMMY_STOCKS:
        if stock["symbol"] not in existing_symbols:
            db.add(
                Stock(
                    symbol=stock["symbol"],
                    name=stock["name"],
                    starting_price=stock["starting_price"],
                    current_price=stock["starting_price"],
                )
            )
    db.flush()

    for stock in db.query(Stock).all():
        market_service.get_config(db, stock)

    if with_history and db.query(PriceData).count() == 0:
        market_service.generate_all(
            db, market_service.DEFAULT_HISTORY_DAYS, seed=market_service.DEFAULT_SEED
        )

    db.commit()
