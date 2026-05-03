"""Kafka event consumer — processor service.

Entry point: ``uvicorn services.processor.main:app``

Architecture:
    uvicorn (port 8002)
    ├─ FastAPI app
    │   ├─ GET /health  (liveness — always 200 while process is alive)
    │   └─ GET /readyz  (readiness — 503 when consumer task is not running)
    └─ lifespan
        ├─ startup: asyncio.create_task(consume(state))
        └─ shutdown: task.cancel() + await
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from libs.platform.logging import setup_json_logger

from .consumer import consume, state
from .routers import ops


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Start the consumer task on startup; cancel it cleanly on shutdown."""
    setup_json_logger("processor")
    logger.info("processor_startup")

    state.task = asyncio.create_task(consume(state))

    yield

    logger.info("processor_shutdown")
    if state.task and not state.task.done():
        state.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await state.task


app = FastAPI(
    title="Processor",
    description="Kafka consumer service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ops.router)
