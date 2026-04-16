"""FastAPI application entry point (async stack)."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.logging import set_cid, setup_logging
from app.database import engine
from app.routers import records


# ---------------------------------------------------------------------------
# Structured JSON logging (setup once at app initialization)
# ---------------------------------------------------------------------------
# setup_logging() configures the root logger; get a named logger for this module
_setup_logging = setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request correlation ID middleware
# ---------------------------------------------------------------------------
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts or generates request correlation ID (cid).

    For each request:
    - Extract cid from X-Correlation-ID header if present
    - Otherwise generate a new UUID
    - Store in context (available via get_cid() for the request lifetime)
    Auto-injects cid into all log messages within this request.
    """

    async def dispatch(self, request: Request, call_next):
        """Extract/generate cid and set in context before handling request."""
        # Try to get cid from X-Correlation-ID header; fallback to new UUID
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        set_cid(cid)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response


# ---------------------------------------------------------------------------
# Lifespan: startup and shutdown events (e.g. for resource management)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Replaces the deprecated `@app.on_event("startup")` pattern.
    Everything before `yield` is startup; after `yield` is shutdown.
    """
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

# Add correlation ID middleware early (runs before route handlers)
app.add_middleware(CorrelationIdMiddleware)

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
