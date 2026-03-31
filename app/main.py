"""FastAPI application entry point (async stack)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.core.logging import setup_logging
from app.database import engine
from app.routers import records


# ---------------------------------------------------------------------------
# Structured JSON logging (setup once at app initialization)
# ---------------------------------------------------------------------------
logger = setup_logging()


# ---------------------------------------------------------------------------
# Lifespan: create tables on startup (idempotent), drop engine on shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    logger.info("startup", extra={"event": "application_started"})
    yield
    await engine.dispose()
    logger.info("shutdown", extra={"event": "engine_disposed"})


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Week 1 data pipeline — **async** SQLAlchemy + asyncpg.",
    lifespan=lifespan,
)

app.include_router(records.router)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "healthy", "version": settings.app_version}


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
