import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.database.session import Base, SessionLocal, engine
from app.routes import articles

logger = logging.getLogger("hn_capstone")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs on server startup, not at import time -- so importing app.main (as the
    # route tests do, via TestClient without a `with` block) never touches the dev DB.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        await articles.seed_if_empty(db)
    yield


app = FastAPI(title="Hacker News Backend Aggregator", lifespan=lifespan)
app.include_router(articles.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
