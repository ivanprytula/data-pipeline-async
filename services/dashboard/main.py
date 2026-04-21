"""Phase 6 — HTMX Dashboard service.

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

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import pages, sse


logger = logging.getLogger(__name__)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info("dashboard_startup")
    yield
    logger.info("dashboard_shutdown")


app = FastAPI(
    title="Data Zoo Dashboard",
    version="0.1.0",
    description="HTMX + Jinja2 server-rendered dashboard for the data-pipeline-async platform.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

app.include_router(pages.router)
app.include_router(sse.router)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
