import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.database.session import SessionLocal
from app.network.openai_client import AiServiceError
from app.routes import ai, articles

logger = logging.getLogger("hn_capstone")


def run_migrations() -> None:
    # Alembic owns dev/prod schema; tests keep create_all (see conftest).
    command.upgrade(Config("alembic.ini"), "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs on server startup, not at import time -- so importing app.main (as the
    # route tests do, via TestClient without a `with` block) never touches the dev DB.
    run_migrations()
    with SessionLocal() as db:
        await articles.seed_if_empty(db)
    yield


app = FastAPI(title="Hacker News Backend Aggregator", lifespan=lifespan)
app.include_router(articles.router)
app.include_router(ai.router)


@app.exception_handler(AiServiceError)
async def ai_service_error_handler(request: Request, exc: AiServiceError):
    logger.warning("AI service unavailable on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=503, content={"detail": "AI service temporarily unavailable"}
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
