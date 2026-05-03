"""Ops endpoints: /health (liveness) and /readyz (readiness)."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, status

from ..constants import INGESTOR_URL, READYZ_CACHE_TTL
from ..http_client import get_http_client


router = APIRouter(tags=["ops"])
logger = logging.getLogger(__name__)

# In-memory cache for /readyz result — avoids hammering ingestor on probe loops
_readyz_cache: dict[str, float | bool] = {"ok": False, "ts": 0.0}


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — process is alive."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness probe — verify ingestor upstream is reachable.

    Result is cached for ``READYZ_CACHE_TTL`` seconds.  Returns 503 when
    ingestor is unreachable so the orchestrator stops routing traffic here.
    """
    now = time.monotonic()
    if now - float(_readyz_cache["ts"]) < READYZ_CACHE_TTL:
        if _readyz_cache["ok"]:
            return {"status": "ready", "ingestor": "ok"}
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "ingestor": "unreachable"},
        )

    client = get_http_client()
    try:
        resp = await client.get(f"{INGESTOR_URL}/health", timeout=2.0)
        resp.raise_for_status()
        _readyz_cache["ok"] = True
        _readyz_cache["ts"] = now
        return {"status": "ready", "ingestor": "ok"}
    except Exception as exc:
        logger.warning("readyz_failed", extra={"reason": str(exc)})
        _readyz_cache["ok"] = False
        _readyz_cache["ts"] = now
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "ingestor": "unreachable"},
        ) from exc
