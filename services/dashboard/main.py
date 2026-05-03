"""Phase 6 — HTMX Dashboard service.

Entry point: ``uvicorn services.dashboard.main:app``

Backend-rendered 3-page dashboard:
  /           Records Explorer (HTMX infinite scroll)
  /search     Semantic Search (calls ai-gateway)
  /metrics    Live Metrics (SSE from ingestor /metrics)
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from libs.platform.logging import setup_json_logger

from .http_client import close_http_client, set_http_client
from .routers import ops, pages, sse


logger = logging.getLogger(__name__)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Create shared HTTP client on startup; close it on shutdown."""
    setup_json_logger("dashboard")
    logger.info("dashboard_startup")
    set_http_client(httpx.AsyncClient(timeout=5.0))
    yield
    logger.info("dashboard_shutdown")
    await close_http_client()


app = FastAPI(
    title="Data Zoo Dashboard",
    version="0.1.0",
    description="HTMX + Jinja2 server-rendered dashboard for the data-pipeline-async platform.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

app.include_router(ops.router)
app.include_router(pages.router)
app.include_router(sse.router)
