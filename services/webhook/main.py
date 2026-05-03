"""Webhook Gateway — FastAPI service on port 8004.

Entry point: ``uvicorn services.webhook.main:app``

Architecture:
    uvicorn (port 8004)
    └─ FastAPI app
        ├─ POST /api/v1/webhooks/{source}           (receive + ingest)
        ├─ GET  /api/v1/webhooks/{source}/{id}      (audit lookup)
        ├─ GET  /admin/sources                      (admin: list sources)
        ├─ POST /admin/sources                      (admin: register source)
        ├─ PATCH /admin/sources/{name}              (admin: pause/resume)
        ├─ GET  /admin/webhooks/events              (admin: event history)
        ├─ POST /admin/webhooks/replay              (admin: bulk replay)
        ├─ GET  /health                             (liveness)
        └─ GET  /readyz                             (readiness)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from services.webhook.routers import admin, health, webhooks
from services.webhook.services.replay_daemon import replay_loop


try:
    from libs.platform.logging import setup_json_logger

    _has_platform_logging = True
except ImportError:
    _has_platform_logging = False

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Start background tasks and configure logging on startup."""
    if _has_platform_logging:
        setup_json_logger("webhook")  # type: ignore[name-defined]
    logger.info("webhook_service_startup")

    # Start replay daemon background task
    replay_task = asyncio.create_task(replay_loop(), name="replay_daemon")

    yield

    # Cancel replay daemon on shutdown and wait for clean exit
    replay_task.cancel()
    with suppress(asyncio.CancelledError):
        await replay_task

    logger.info("webhook_service_shutdown")


app = FastAPI(
    title="Webhook Gateway",
    description="Event ingestion gateway for external webhook sources",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(webhooks.router)
app.include_router(admin.router)
app.include_router(health.router)
