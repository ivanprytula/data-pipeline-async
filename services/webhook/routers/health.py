"""Health and readiness endpoints for the webhook service.

Follows the liveness / readiness probe convention used by all services in
this project. Imported into ``main.py``; replaces the inline /health and
/readyz stubs.

Liveness  (/health): process is alive — returns 200 immediately.
Readiness (/readyz): service can handle traffic — checks:
  - PostgreSQL connectivity (mandatory)
  - Kafka connectivity (optional — degraded not failing)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    """Liveness probe — returns 200 as long as the process is alive."""
    return JSONResponse({"status": "ok"})


@router.get("/readyz", include_in_schema=False)
async def readyz() -> JSONResponse:
    """Readiness probe — checks PostgreSQL and Kafka connectivity.

    Returns:
        200 ``{"status": "ready"}`` when all mandatory checks pass.
        503 ``{"status": "degraded", "checks": {...}}`` if Postgres fails.
    """
    checks: dict[str, str] = {}
    all_healthy = True

    # Check PostgreSQL connectivity
    postgres_ok = await _check_postgres()
    checks["postgres"] = "ok" if postgres_ok else "unavailable"
    if not postgres_ok:
        all_healthy = False

    # Check Kafka connectivity (non-blocking — service degrades but stays ready)
    kafka_ok = await _check_kafka()
    checks["kafka"] = "ok" if kafka_ok else "unavailable"

    if all_healthy:
        return JSONResponse({"status": "ready", "checks": checks})

    return JSONResponse(
        {"status": "degraded", "checks": checks},
        status_code=503,
    )


async def _check_postgres() -> bool:
    """Verify PostgreSQL is reachable by executing a trivial query."""
    try:
        from sqlalchemy import text

        from services.webhook.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("health_postgres_check_failed", extra={"error": str(exc)})
        return False


async def _check_kafka() -> bool:
    """Verify Kafka producer can connect to the broker."""
    try:
        from services.webhook.services.kafka_publisher import is_kafka_healthy

        return await is_kafka_healthy()
    except Exception as exc:
        logger.warning("health_kafka_check_failed", extra={"error": str(exc)})
        return False
