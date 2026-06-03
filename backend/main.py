import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from database import init_db, SessionLocal
import models  # noqa: F401 — registers ORM models with Base.metadata
from models import Account
from routers import customers, sync, alarms
from scheduler import setup_scheduler, stop_scheduler, is_scheduler_running

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    setup_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Alarm Dashboard", lifespan=lifespan)


# ── Exception handlers ────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ── Routers ───────────────────────────────────────────────────

app.include_router(customers.router, prefix="/api")
app.include_router(sync.router,      prefix="/api")
app.include_router(alarms.router,    prefix="/api")


# ── Health endpoint ───────────────────────────────────────────

@app.get("/health")
def health():
    db_status  = "ok"
    last_sync  = None

    try:
        db = SessionLocal()
        try:
            row = db.query(func.max(Account.last_sync_at)).scalar()
            last_sync = row.isoformat() if row else None
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"[health] DB check failed: {exc}")
        db_status = "error"

    return {
        "status":    "ok",
        "scheduler": "running" if is_scheduler_running() else "stopped",
        "db":        db_status,
        "last_sync": last_sync,
    }
