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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from services.ingestor.constants import (
    CACHE_KEY_LIST_PREFIX,
    CACHE_KEY_RECORD,
    CACHE_LIST_MAX_LIMIT,
    CACHE_LIST_MAX_SKIP,
    CACHE_LOCK_DEFAULT_TTL_SECONDS,
    CACHE_LOCK_PREFIX,
    CACHE_TTL_LIST,
    CACHE_TTL_RECORD,
)


if TYPE_CHECKING:
    from services.ingestor.schemas import RecordResponse


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
    await _client.ping()  # type: ignore
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
        from services.ingestor.schemas import RecordResponse

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
        from services.ingestor.metrics import cache_errors_total

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
        from services.ingestor.metrics import cache_errors_total

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
        from services.ingestor.metrics import cache_errors_total

        cache_errors_total.labels(operation="invalidate").inc()


# ── Phase 13.4: List cache ─────────────────────────────────────────────────


def _list_cache_key(source: str, skip: int, limit: int) -> str:
    """Build list cache key for a paginated query.

    Args:
        source: Record source name.
        skip: Pagination offset.
        limit: Page size.

    Returns:
        Redis key string.
    """
    return f"{CACHE_KEY_LIST_PREFIX}:{source}:{skip}:{limit}"


def _should_skip_list_cache(skip: int, limit: int) -> bool:
    """Return True when caching the list page would waste memory or miss too often."""
    return skip > CACHE_LIST_MAX_SKIP or limit > CACHE_LIST_MAX_LIMIT


async def get_records_list(source: str, skip: int, limit: int) -> list | None:
    """Return a cached list of records for the given source/skip/limit, or None.

    Args:
        source: Record source filter.
        skip: Pagination offset.
        limit: Page size.

    Returns:
        Deserialized list, or None on cache miss / skip.
    """
    import json

    if _client is None or _should_skip_list_cache(skip, limit):
        return None

    try:
        key = _list_cache_key(source, skip, limit)
        raw = await _client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning(
            "cache_list_get_error",
            extra={"source": source, "skip": skip, "limit": limit, "error": str(e)},
        )
        return None


async def set_records_list(source: str, skip: int, limit: int, data: list) -> None:
    """Persist a paginated list to cache with a short TTL.

    Args:
        source: Record source filter.
        skip: Pagination offset.
        limit: Page size.
        data: Serialisable list of record dicts.
    """
    import json

    if _client is None or _should_skip_list_cache(skip, limit):
        return

    try:
        key = _list_cache_key(source, skip, limit)
        await _client.set(key, json.dumps(data), ex=CACHE_TTL_LIST)
    except Exception as e:
        logger.warning(
            "cache_list_set_error",
            extra={"source": source, "skip": skip, "limit": limit, "error": str(e)},
        )


async def invalidate_records_list_by_source(source: str) -> None:
    """Delete all list cache entries for a given source using SCAN.

    Args:
        source: Source name whose list pages should be evicted.
    """
    if _client is None:
        return

    try:
        pattern = f"{CACHE_KEY_LIST_PREFIX}:{source}:*"
        keys: list[bytes] = []
        async for key in _client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await _client.delete(*keys)
            logger.info(
                "cache_list_invalidated",
                extra={"source": source, "deleted_keys": len(keys)},
            )
    except Exception as e:
        logger.warning(
            "cache_list_invalidate_error",
            extra={"source": source, "error": str(e)},
        )


# ── Phase 13.4: Distributed lock ──────────────────────────────────────────────


@asynccontextmanager
async def redis_lock(
    name: str,
    ttl_seconds: int = CACHE_LOCK_DEFAULT_TTL_SECONDS,
) -> AsyncGenerator[bool]:
    """Async context manager providing a non-blocking distributed lock (SET NX PX).

    Uses a single Redis SET NX PX command — safe and atomic on a single Redis node.
    Does NOT block waiting for the lock; yields ``False`` immediately if not acquired.

    Usage::

        async with redis_lock("job:daily_rollup") as acquired:
            if not acquired:
                return  # another instance holds the lock; skip this run

    Args:
        name: Lock identifier (will be prefixed with ``dp:lock:``).
        ttl_seconds: Lock expiry in seconds (prevents deadlock on crash).

    Yields:
        True if the lock was acquired; False otherwise.
    """
    if _client is None:
        # No Redis — yield True so jobs still run in single-instance deployments.
        yield True
        return

    lock_key = f"{CACHE_LOCK_PREFIX}:{name}"
    acquired = await _client.set(lock_key, "1", nx=True, ex=ttl_seconds)
    try:
        yield bool(acquired)
    finally:
        if acquired:
            try:
                await _client.delete(lock_key)
            except Exception as e:
                logger.warning(
                    "redis_lock_release_error",
                    extra={"lock": name, "error": str(e)},
                )
