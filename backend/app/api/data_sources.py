import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..adapters.angel_one_auth import AngelOneAuthError
from ..db import get_db
from ..schemas import BrokerImportItem, BrokerImportOut, BrokerImportRequest, DataSourceOut
from ..services import data_sources, market_service

router = APIRouter()


@router.get("/data-sources", response_model=list[DataSourceOut])
def list_data_sources():
    """The brokers stocks can be imported from, and whether each is set up in .env."""
    return data_sources.source_status()


@router.post("/data-sources/import", response_model=BrokerImportOut)
def import_from_data_source(body: BrokerImportRequest, db: Session = Depends(get_db)):
    """Fetch daily candles for each symbol from a broker and store them like any other stock.
    Credentials are read from .env on the server; none are accepted from, or returned to, the page."""
    if body.years is not None and body.source != "upstox":
        raise HTTPException(status_code=400, detail="Years of history can only be chosen for Upstox.")

    symbols = list(dict.fromkeys(s.strip().upper() for s in body.symbols if s.strip()))
    if not symbols:
        raise HTTPException(status_code=400, detail="Enter at least one symbol.")

    try:
        adapter, close = data_sources.open_adapter(body.source, body.years)
    except data_sources.SourceNotConfigured as err:
        raise HTTPException(status_code=400, detail=str(err)) from None
    except (AngelOneAuthError, httpx.HTTPError) as err:
        raise HTTPException(status_code=400, detail=f"Couldn't sign in to the broker: {err}") from None

    try:
        outcomes = data_sources.import_symbols(db, adapter, symbols, source=body.source, merge=body.merge)
    finally:
        close()

    results = [
        BrokerImportItem(
            symbol=o.symbol,
            ok=o.ok,
            name=o.name,
            candles_stored=o.candles,
            first_date=o.first_date,
            last_date=o.last_date,
            current_price=o.current_price,
            error=o.error,
        )
        for o in outcomes
    ]
    imported = sum(1 for r in results if r.ok)
    return BrokerImportOut(
        source=body.source,
        results=results,
        imported=imported,
        failed=len(results) - imported,
        market_date=market_service.latest_market_date(db),
    )
