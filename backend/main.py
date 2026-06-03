import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from database import init_db
import models  # noqa: F401 — registers ORM models with Base.metadata
from routers import customers, sync, alarms
from scheduler import setup_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    setup_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Alarm Dashboard", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


app.include_router(customers.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(alarms.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
