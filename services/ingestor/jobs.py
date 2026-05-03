"""Ingestion job templates for scheduled and API-driven data ingestion.

Demonstrates both short-running API ingestion and long-running scheduled batch jobs.

Designed for:
- Multiple data sources (easily extensible)
- Data warehouse/datalake integration (idempotent, incremental)
- Future scaling to Celery/arq (job interface remains unchanged)

Job patterns:
1. API ingestion (short): sync on write, deduplication via unique constraint
2. Scheduled batch (long): periodic fetch from external source, retry on failure
3. Archive job (background): move data to cold storage (Pillar 2 archival strategy)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.ingestor import crud
from services.ingestor.core.retry import IdempotencyKeyTracker, exponential_backoff
from services.ingestor.models import Record
from services.ingestor.schemas import RecordRequest


logger = logging.getLogger(__name__)


# Global deduplication tracker (in-memory for single-instance; Redis for distributed)
_dedup_tracker = IdempotencyKeyTracker(ttl_seconds=3600)


# ============================================================================
# API Ingestion Jobs (Short-Running)
# ============================================================================


async def ingest_api_single(
    db: AsyncSession,
    request: RecordRequest,
    idempotency_key: str | None = None,
) -> Record | None:
    """Ingest a single record from API (sync on write).

    This is the API ingestion pattern: immediate write + response.

    Args:
        db: Active async database session.
        request: RecordRequest payload from API.
        idempotency_key: Optional key for deduplication (prevents double-writes on retry).

    Returns:
        Inserted Record ORM instance, or None if duplicate (with idempotency_key).

    Notes:
        - Deduplication is in-memory (per-process). For distributed systems, use database
          unique constraints (already enforced on source + timestamp).
        - Uses connection from request lifespan, not a scheduled job.
    """
    if idempotency_key:
        if _dedup_tracker.is_duplicate(idempotency_key):
            logger.info(
                "ingest_duplicate_skipped",
                extra={
                    "idempotency_key": idempotency_key,
                    "source": request.source,
                },
            )
            return None
        _dedup_tracker.mark_seen(idempotency_key)

    record = await crud.create_record(db, request)

    logger.info(
        "ingest_api_single_created",
        extra={
            "record_id": record.id,
            "source": record.source,
            "idempotency_key": idempotency_key,
        },
    )

    return record


async def ingest_api_batch(
    db: AsyncSession,
    requests: list[RecordRequest],
    idempotency_key_prefix: str | None = None,
) -> dict[str, Any]:
    """Ingest a batch of records from API (bulk insert, optimized).

    API ingestion pattern for bulk uploads: batch insert + summary response.

    Args:
        db: Active async database session.
        requests: List of RecordRequest payloads.
        idempotency_key_prefix: Optional prefix for batch deduplication.

    Returns:
        Summary dict: {inserted: count, errors: count, first_error: str | None}.

    Notes:
        - Uses bulk insert with RETURNING for efficiency (1 round-trip).
        - Skips duplicates if idempotency_key_prefix is provided.
    """
    batch_key = (
        f"{idempotency_key_prefix}:{len(requests)}" if idempotency_key_prefix else None
    )

    if batch_key and _dedup_tracker.is_duplicate(batch_key):
        logger.info(
            "ingest_batch_duplicate_skipped",
            extra={"batch_key": batch_key, "count": len(requests)},
        )
        return {
            "inserted": 0,
            "errors": 0,
            "first_error": "Batch already processed (duplicate key)",
        }

    if batch_key:
        _dedup_tracker.mark_seen(batch_key)

    try:
        records = await crud.create_records_batch(db, requests)
        logger.info(
            "ingest_api_batch_created",
            extra={
                "inserted": len(records),
                "batch_key": batch_key,
                "sources": set(r.source for r in records),
            },
        )
        return {"inserted": len(records), "errors": 0, "first_error": None}

    except Exception as e:
        logger.error(
            "ingest_api_batch_failed",
            extra={
                "batch_key": batch_key,
                "count": len(requests),
                "error": str(e),
            },
        )
        return {"inserted": 0, "errors": len(requests), "first_error": str(e)}


# ============================================================================
# Scheduled Batch Jobs (Long-Running) — Templates for Future Sources
# ============================================================================


@exponential_backoff(max_retries=3, base_delay=2.0, max_delay=60.0)
async def ingest_scheduled_batch_example(db: AsyncSession) -> dict[str, Any]:
    """Template for a scheduled batch ingestion job (runs every X hours).

    This is a placeholder job that demonstrates the pattern. For each new data source,
    create a similar job:
    1. Fetch from external source (API, S3, Kafka, etc)
    2. Transform to RecordRequest list
    3. Bulk insert with deduplication
    4. Return metrics

    Args:
        db: Active async database session (injected by scheduler).

    Returns:
        Summary dict: {source: str, inserted: count, duration_seconds: float}.

    Example usage in scheduler:

        @scheduler.job(
            name="ingest_source_a_hourly",
            trigger=IntervalTrigger(hours=1),
            max_retries=3,
            timeout_seconds=300,
            tags={"batch", "high_volume"},
        )
        async def ingest_source_a(db: AsyncSession) -> dict[str, Any]:
            return await ingest_scheduled_batch_template(
                db,
                source="source_a",
                fetch_fn=fetch_from_api_source_a,
                batch_size=1000,
            )
    """
    import time

    from services.ingestor.cache import redis_lock

    async with redis_lock("job:ingest_scheduled_batch_example") as acquired:
        if not acquired:
            logger.info(
                "job_skipped_lock_held",
                extra={"job": "ingest_scheduled_batch_example"},
            )
            return {"source": "example_source", "skipped": True, "reason": "lock_held"}

        start_time = time.perf_counter()

        # 1. Fetch external data (stub for example)
        source_name = "example_source"
        records_data = [
            {
                "source": source_name,
                "timestamp": datetime.now(UTC),
                "data": {"example": "data"},
                "tags": ["batch"],
            }
        ]

        # 2. Transform to RecordRequest
        requests = [RecordRequest(**r) for r in records_data]

        # 3. Bulk insert
        batch_result = await ingest_api_batch(
            db,
            requests,
            idempotency_key_prefix=f"{source_name}_{datetime.now(UTC).date()}",
        )

        duration = time.perf_counter() - start_time

        result = {
            "source": source_name,
            "inserted": batch_result["inserted"],
            "errors": batch_result["errors"],
            "duration_seconds": duration,
        }

        logger.info(
            "ingest_scheduled_batch_completed",
            extra=result,
        )

        return result


@exponential_backoff(max_retries=2, base_delay=5.0)
async def archive_old_records(db: AsyncSession) -> dict[str, Any]:
    """Scheduled job to move old records to cold storage (Pillar 2 archival).

    Runs daily to move records >30 days old to records_archive partitions.

    Args:
        db: Active async database session (injected by scheduler).

    Returns:
        Summary dict: {archived: count, deleted: count, duration_seconds: float}.

    Notes:
        - Works in tandem with Pillar 2 data retention strategy.
        - For implementation: UPDATE records SET archive_date=NOW()
          WHERE created_at < NOW() - INTERVAL '30 days'
        - Placeholder for now (Pillar 5 implementation).
    """
    from services.ingestor.cache import redis_lock

    async with redis_lock("job:archive_old_records", ttl_seconds=600) as acquired:
        if not acquired:
            logger.info("job_skipped_lock_held", extra={"job": "archive_old_records"})
            return {
                "archived": 0,
                "deleted": 0,
                "duration_seconds": 0.0,
                "skipped": True,
            }

        # TODO: Implement archive logic using data-retention-archival.md strategy
        logger.info(
            "archive_old_records_placeholder",
            extra={"status": "pending_implementation"},
        )
        return {
            "archived": 0,
            "deleted": 0,
            "duration_seconds": 0.0,
            "status": "placeholder (Pillar 5)",
        }


# ============================================================================
# Health Check Helpers
# ============================================================================


async def get_ingestion_health(db: AsyncSession) -> dict[str, Any]:
    """Get ingestion pipeline health status.

    Used by `/health/ingestion` endpoint for monitoring and alerting.

    Returns:
        Dict with: records_count, last_record_time, api_insert_latency_ms, etc.
    """
    try:
        # Count recent records (last 24 hours)
        stmt = select(Record).where(
            Record.created_at >= datetime.now(UTC) - timedelta(days=1)
        )
        result = await db.execute(stmt)
        records_24h = len(result.scalars().all())

        # Get last record timestamp
        stmt = select(Record).order_by(Record.created_at.desc()).limit(1)
        result = await db.execute(stmt)
        last_record = result.scalar_one_or_none()
        last_record_time = last_record.created_at if last_record else None

        return {
            "status": "healthy",
            "records_24h": records_24h,
            "last_record_time": last_record_time.isoformat()
            if last_record_time
            else None,
            "ingestion_enabled": True,
        }

    except Exception:
        logger.exception("ingestion_health_check_failed")
        return {
            "status": "unhealthy",
            "error": "Internal ingestion health check failure",
            "ingestion_enabled": False,
        }
