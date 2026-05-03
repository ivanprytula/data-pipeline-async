"""Ops endpoints: /health (liveness) and /readyz (readiness)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from ..consumer import state


router = APIRouter(tags=["ops"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict[str, str | bool | int]:
    """Liveness probe — process is alive while the event loop is running."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str | bool | int]:
    """Readiness probe — 503 until the Kafka consumer task is running."""
    if not state.started:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "starting", "consumer_started": False},
        )
    return {
        "status": "ready",
        "consumer_started": state.started,
        "messages_consumed": state.messages_consumed,
        "messages_failed": state.messages_failed,
    }
