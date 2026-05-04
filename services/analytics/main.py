"""Query API — Read-only CQRS analytics service.

Entry point: ``uvicorn services.analytics.main:app``
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from libs.platform.logging import setup_json_logger

from .database import engine
from .routers import analytics, ops


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Configure logging, verify DB connection on startup; dispose engine on shutdown."""
    setup_json_logger("analytics")
    logger.info("analytics_starting")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("analytics_db_connected")
    except Exception as exc:
        logger.error("analytics_db_connect_failed", extra={"error": str(exc)})
        raise

    yield

    logger.info("analytics_shutting_down")
    await engine.dispose()


app = FastAPI(
    title="Query API — Analytics Read Side",
    description="CQRS read-optimized service. Read-only access to PostgreSQL.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ops.router)
app.include_router(analytics.router)
