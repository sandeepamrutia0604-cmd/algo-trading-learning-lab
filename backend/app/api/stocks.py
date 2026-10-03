from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..adapters.csv_candles import parse_candles
from ..db import get_db
from ..models import PriceData, Stock
from ..schemas import PracticeStockRequest, StockImportOut, StockImportRequest, StockOut
from ..services import market_service, practice_stocks
from ..services.real_stocks import import_candles

router = APIRouter()


def _stock_out(db: Session, stock: Stock) -> StockOut:
    closes = market_service.recent_closes(db, stock.id)
    return StockOut(
        symbol=stock.symbol,
        name=stock.name,
        starting_price=stock.starting_price,
        current_price=stock.current_price,
        previous_close=closes[-2] if len(closes) >= 2 else None,
        recent_closes=closes,
        source=stock.source,
        removable=practice_stocks.is_removable(stock),
    )


@router.get("/stocks", response_model=list[StockOut])
def list_stocks(db: Session = Depends(get_db)):
    return [_stock_out(db, stock) for stock in db.query(Stock).order_by(Stock.symbol).all()]


@router.post("/stocks/practice", response_model=StockOut)
def create_practice_stock(body: PracticeStockRequest, db: Session = Depends(get_db)):
    """Create a made-up stock whose prices the simulator generates (see services/practice_stocks.py)."""
    stock = practice_stocks.create(db, body.symbol, body.name, body.starting_price, body.model, body.volatility, body.trend)
    return _stock_out(db, stock)


@router.delete("/stocks/{symbol}")
def delete_practice_stock(symbol: str, db: Session = Depends(get_db)):
    practice_stocks.delete(db, symbol)
    return {"deleted": symbol.strip().upper()}


@router.post("/stocks/import", response_model=StockImportOut)
def import_stock(body: StockImportRequest, db: Session = Depends(get_db)):
    """Import daily candles from the text of an uploaded CSV/TSV file (see adapters/csv_candles.py)."""
    symbol = body.symbol.upper()
    created = db.query(Stock).filter(Stock.symbol == symbol).first() is None
    try:
        candles = parse_candles(body.csv_text)
        stock = import_candles(db, symbol, body.name, candles, source="csv", replace=body.replace)
        db.commit()
    except ValueError as err:  # CsvImportError is a ValueError
        db.rollback()
        raise HTTPException(status_code=400, detail=str(err)) from None

    return StockImportOut(
        symbol=stock.symbol,
        name=stock.name,
        created=created,
        candles_read=len(candles),
        candles_stored=db.query(PriceData).filter(PriceData.stock_id == stock.id).count(),
        first_date=candles[0].date,
        last_date=candles[-1].date,
        current_price=stock.current_price,
        market_date=market_service.latest_market_date(db),
    )
