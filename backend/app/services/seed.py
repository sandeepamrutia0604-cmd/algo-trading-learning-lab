from sqlalchemy.orm import Session

from ..models import Portfolio, Stock

DUMMY_STOCKS = [
    {"symbol": "ALPHA", "name": "Alpha Industries", "starting_price": 100.0},
    {"symbol": "BETA", "name": "Beta Technologies", "starting_price": 250.0},
    {"symbol": "GAMMA", "name": "Gamma Foods", "starting_price": 75.0},
    {"symbol": "DELTA", "name": "Delta Motors", "starting_price": 500.0},
]


def ensure_seed_data(db: Session) -> None:
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

    db.commit()
