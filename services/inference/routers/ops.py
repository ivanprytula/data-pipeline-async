"""Ops endpoints: /health (liveness) and /readyz (readiness)."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, status

from ..constants import QDRANT_URL
from ..schemas import HealthResponse
from ..state import get_vector_store


router = APIRouter(tags=["ops"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe — process is alive (no upstream check)."""
    from ..state import _instance  # noqa: PLC0415

    return HealthResponse(status="ok", qdrant_connected=_instance is not None)


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness probe — verify Qdrant is reachable before serving traffic.

    Returns 503 when Qdrant is unreachable.  Never restarts the container
    (that is ``/health``'s job).
    """
    get_vector_store()  # raises 503 if not initialised
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{QDRANT_URL}/healthz")
            resp.raise_for_status()
        return {"status": "ready", "qdrant": "ok"}
    except Exception as exc:
        logger.warning("readyz_failed", extra={"reason": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "qdrant": "unreachable"},
        ) from exc
