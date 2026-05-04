"""Ops endpoints: /health (liveness) and /readyz (readiness)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from ..database import AsyncSessionLocal


router = APIRouter(tags=["ops"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — process is alive."""
    return {"status": "healthy", "service": "analytics"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness probe — verify database connectivity before serving traffic."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception as exc:
        logger.warning("readyz_failed", extra={"reason": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "db": "unreachable"},
        ) from exc
