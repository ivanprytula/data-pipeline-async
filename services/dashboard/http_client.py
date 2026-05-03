"""Shared httpx.AsyncClient singleton for dashboard.

``set_http_client`` / ``close_http_client`` are called from the lifespan.
``get_http_client`` is used by routers that need the shared client.
"""

from __future__ import annotations

import httpx
from fastapi import HTTPException, status


_instance: httpx.AsyncClient | None = None


def set_http_client(client: httpx.AsyncClient) -> None:
    """Store the shared client (called from lifespan startup)."""
    global _instance
    _instance = client


async def close_http_client() -> None:
    """Close and discard the shared client (called from lifespan shutdown)."""
    global _instance
    if _instance is not None:
        await _instance.aclose()
        _instance = None


def get_http_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient or raise 503 if not yet initialised."""
    if _instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "reason": "http_client_not_initialized"},
        )
    return _instance
