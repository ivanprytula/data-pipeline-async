"""FastAPI application entry point (async stack)."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse

from app import cache
from app.auth import verify_docs_credentials
from app.config import settings
from app.constants import HEALTH_RATE_LIMIT
from app.core.logging import set_cid, setup_logging
from app.database import engine, get_db
from app.fetch import close_http_client
from app.fetch_aiohttp import close_http_session
from app.metrics import (  # noqa: F401 — imported to register metrics at startup
    batch_size_histogram,
    enrich_duration_seconds,
    records_created_total,
    records_upsert_conflicts_total,
)
from app.rate_limiting import limiter
from app.routers import records, records_v2


# Type alias for database dependency
type DbDep = Annotated[AsyncSession, Depends(get_db)]


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
async def lifespan(app: FastAPI):
    """Replaces the deprecated `@app.on_event("startup")` pattern.
    Everything before `yield` is startup; after `yield` is shutdown.
    """
    logger.info("startup", extra={"event": "application_started"})

    # Startup: connect Redis if enabled
    if settings.redis_enabled:
        try:
            await cache.connect_cache(settings.redis_url)
        except Exception as e:
            logger.warning(
                "redis_startup_failed",
                extra={"error": str(e)},
            )
            # Non-fatal: cache is optional, app continues without it

    yield

    # Shutdown: cleanup resources (cleanup order: app-level clients first, then Redis, then engine)
    await close_http_client()  # httpx client cleanup
    await close_http_session()  # aiohttp session cleanup
    await cache.disconnect_cache()  # Redis cleanup (safe even if not connected)
    await engine.dispose()  # Database connections cleanup
    logger.info("shutdown", extra={"event": "engine_disposed"})


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
# If docs_username/docs_password are configured, disable default docs
# (they'll be handled by protected endpoints below)
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Async data pipeline — SQLAlchemy 2.0 + asyncpg.\n\n"
        "**Rate-limiting showcase** (create-record variations):\n"
        "- `POST /api/v1/records` — fixed window, IP-based (slowapi default)\n"
        "- `POST /api/v2/records/token-bucket` — token bucket (burst-tolerant)\n"
        "- `POST /api/v2/records/sliding-window` — exact sliding window"
    ),
    lifespan=lifespan,
    docs_url=None if settings.docs_username else "/docs",
    redoc_url=None if settings.docs_username else "/redoc",
    openapi_url=None if settings.docs_username else "/openapi.json",
)

# Attach limiter to app (required by slowapi)
app.state.limiter = limiter

# Prometheus: register /metrics endpoint and instrument all HTTP routes.
# Must be called at module level (not inside lifespan) so the route is
# registered immediately — ASGITransport in tests does not trigger lifespan.
Instrumentator().instrument(app).expose(app, include_in_schema=False, tags=["ops"])


# Add rate limit exception handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded (429 Too Many Requests)."""
    logger.warning("rate_limit_exceeded", extra={"path": request.url.path})
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
    )


# ---------------------------------------------------------------------------
# Protected Documentation Endpoints (if auth is configured)
# ---------------------------------------------------------------------------
if settings.docs_username and settings.docs_password:
    """If docs auth is configured, protect Swagger UI, ReDoc, and OpenAPI schema."""

    @app.get(
        "/docs",
        include_in_schema=False,
        dependencies=[Depends(verify_docs_credentials)],
    )
    async def get_swagger_ui() -> HTMLResponse:
        """Protected Swagger UI endpoint."""
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{settings.app_name} - Swagger UI",
        )

    @app.get(
        "/redoc",
        include_in_schema=False,
        dependencies=[Depends(verify_docs_credentials)],
    )
    async def get_redoc() -> HTMLResponse:
        """Protected ReDoc endpoint."""
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{settings.app_name} - ReDoc",
        )

    @app.get(
        "/openapi.json",
        include_in_schema=False,
        dependencies=[Depends(verify_docs_credentials)],
    )
    async def get_openapi_schema() -> dict:
        """Protected OpenAPI schema endpoint."""
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=settings.app_name,
            version=settings.app_version,
            description=app.description,
            routes=app.routes,
        )
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    logger.info(
        "docs_auth_enabled",
        extra={"docs_endpoints": ["/docs", "/redoc", "/openapi.json"]},
    )


# Add correlation ID middleware early (runs before route handlers)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(records.router)
app.include_router(records_v2.router)


# ---------------------------------------------------------------------------
# Health & Readiness Probes
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
@limiter.limit(HEALTH_RATE_LIMIT)
async def health(request: Request) -> dict[str, str]:
    """Liveness probe — process is alive (no DB check).

    Used by Kubernetes to decide whether to restart the container.
    Should be lightweight and not depend on external services.
    Rate-limited to prevent health check DoS attacks.
    """
    return {"status": "healthy", "version": settings.app_version}


@app.get("/readyz", tags=["ops"])
async def readyz(db: DbDep) -> dict[str, str]:
    """Readiness probe — DB reachable, pod can serve traffic.

    Used by Kubernetes to decide whether to route traffic to this pod.
    If DB is unreachable, returns 503 to pull this pod from load balancer.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception as e:
        logger.warning("readyz_failed", extra={"reason": str(e)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "db": "unreachable"},
        ) from e


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
