"""FastAPI application entry point (async stack)."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.auth import verify_docs_credentials
from app.config import settings
from app.constants import HEALTH_RATE_LIMIT
from app.core.logging import set_cid, setup_logging
from app.database import engine
from app.rate_limiting import limiter
from app.routers import records, records_v2


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
    async def get_swagger_ui() -> str:
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
    async def get_redoc() -> str:
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
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
@limiter.limit(HEALTH_RATE_LIMIT)
async def health(request: Request) -> dict[str, str]:
    return {"status": "healthy", "version": settings.app_version}


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
