"""Async Redis caching layer — fail-open on connection errors.

This module provides a read cache for single-record lookups. All cache
operations are wrapped in try/except to prevent Redis failures from affecting
the API (fail-open pattern).

Pattern inspired by database.py singleton style:
- Module-level _client singleton
- connect_cache() / disconnect_cache() in lifespan
- All functions are pure async

Observability:
- All cache errors log warnings and increment cache_errors_total counter
- Hits/misses tracked via prometheus counters in metrics.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.constants import CACHE_KEY_RECORD, CACHE_TTL_RECORD


if TYPE_CHECKING:
    from app.schemas import RecordResponse


# singleton instance (initialized in lifespan startup)
_client: Redis | None = None


logger = logging.getLogger(__name__)


async def connect_cache(redis_url: str) -> None:
    """Initialize Redis connection.

    Args:
        redis_url: Redis DSN (e.g., redis://localhost:6379/0)

    Raises:
        Exception: If Redis connection fails (will be caught at startup)
    """
    global _client
    _client = Redis.from_url(redis_url, decode_responses=True)
    # Ping to verify connection
    await _client.ping()
    logger.info("cache_connected", extra={"url": redis_url})


async def disconnect_cache() -> None:
    """Close Redis connection."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
    logger.info("cache_disconnected")


async def get_record(record_id: int) -> RecordResponse | None:
    """Retrieve a cached record by ID.

    Args:
        record_id: Record primary key

    Returns:
        RecordResponse if found in cache and valid JSON, else None

    Fails open: returns None on any error (connection, deserialization)
    """
    if _client is None:
        return None

    try:
        from app.schemas import RecordResponse

        key = CACHE_KEY_RECORD.format(record_id=record_id)
        cached_json = await _client.get(key)
        if cached_json is None:
            return None
        # Deserialize from JSON via Pydantic
        return RecordResponse.model_validate_json(cached_json)
    except Exception as e:
        logger.warning(
            "cache_get_error",
            extra={"record_id": record_id, "error": str(e)},
        )
        from app.metrics import cache_errors_total

        cache_errors_total.labels(operation="get").inc()
        return None


async def set_record(
    record_id: int, record: RecordResponse, ttl: int = CACHE_TTL_RECORD
) -> None:
    """Store a record in cache.

    Args:
        record_id: Record primary key
        record: RecordResponse instance (will be JSON serialized)
        ttl: Time-to-live in seconds (default: 1 hour)

    Fails open: logs warning + increments error counter on failure
    """
    if _client is None:
        return

    try:
        key = CACHE_KEY_RECORD.format(record_id=record_id)
        json_data = record.model_dump_json()
        await _client.setex(key, ttl, json_data)
        logger.info("cache_set", extra={"record_id": record_id, "ttl": ttl})
    except Exception as e:
        logger.warning(
            "cache_set_error",
            extra={"record_id": record_id, "error": str(e)},
        )
        from app.metrics import cache_errors_total

        cache_errors_total.labels(operation="set").inc()


async def invalidate_record(record_id: int) -> None:
    """Delete a cached record.

    Args:
        record_id: Record primary key to invalidate

    Fails open: logs warning + increments error counter on failure
    """
    if _client is None:
        return

    try:
        key = CACHE_KEY_RECORD.format(record_id=record_id)
        await _client.delete(key)
        logger.info("cache_invalidate", extra={"record_id": record_id})
    except Exception as e:
        logger.warning(
            "cache_invalidate_error",
            extra={"record_id": record_id, "error": str(e)},
        )
        from app.metrics import cache_errors_total

        cache_errors_total.labels(operation="invalidate").inc()
