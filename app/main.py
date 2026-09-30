import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.database.session import Base, engine
from app.routes import articles

logger = logging.getLogger("hn_capstone")

Base.metadata.create_all(engine)

app = FastAPI(title="Hacker News Backend Aggregator")
app.include_router(articles.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
