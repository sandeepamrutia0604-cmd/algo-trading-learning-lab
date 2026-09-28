import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.analytics import router as analytics_router
from .api.backtests import router as backtests_router
from .api.health import router as health_router
from .api.market import router as market_router
from .api.orders import router as orders_router
from .api.portfolio import router as portfolio_router
from .api.risk import router as risk_router
from .api.simulation import router as simulation_router
from .api.stocks import router as stocks_router
from .api.strategies import router as strategies_router
from .api.trades import router as trades_router
from .config import settings
from .db import Base, SessionLocal, engine
from .logging_config import configure_logging
from .migrations import ensure_columns
from .services.exceptions import StockNotFoundError, StrategyNotFoundError, TradingError
from .services.seed import ensure_seed_data

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)
    db = SessionLocal()
    try:
        ensure_seed_data(db)
    finally:
        db.close()
    logger.info("%s starting up", settings.app_name)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(TradingError)
def trading_error_handler(request: Request, exc: TradingError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(StockNotFoundError)
def stock_not_found_handler(request: Request, exc: StockNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(StrategyNotFoundError)
def strategy_not_found_handler(request: Request, exc: StrategyNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


app.include_router(health_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(stocks_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(trades_router, prefix="/api")
app.include_router(simulation_router, prefix="/api")
app.include_router(strategies_router, prefix="/api")
app.include_router(backtests_router, prefix="/api")
app.include_router(risk_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
