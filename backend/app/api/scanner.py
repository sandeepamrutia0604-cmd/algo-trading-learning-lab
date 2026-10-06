from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import ScanOut, ScanRequest
from ..services import backtest_service, market_service, scanner_service

router = APIRouter()


@router.post("/scanner/run", response_model=ScanOut)
def run_scan(body: ScanRequest, db: Session = Depends(get_db)):
    """Which stocks is this strategy signalling right now (as of the market clock)? Changes nothing."""
    defn, params = backtest_service.resolve_definition(body.type, body.params, body.rules)
    rows = scanner_service.scan(db, defn, params)
    return ScanOut(
        market_date=market_service.latest_market_date(db),
        strategy=defn.name_fn(params),
        scanned=len(rows),
        buy_today=sum(1 for r in rows if r["signal_today"] and r["signal_today"]["side"] == "BUY"),
        sell_today=sum(1 for r in rows if r["signal_today"] and r["signal_today"]["side"] == "SELL"),
        in_trade=sum(1 for r in rows if r["state"] == "in"),
        rows=rows,
    )
