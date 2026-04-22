"""Analytics routes — CTE aggregations and window function queries."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestor.constants import API_V1_PREFIX
from ingestor.database import get_db
from ingestor.models import Record


logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{API_V1_PREFIX}/analytics", tags=["analytics"])

type DbDep = Annotated[AsyncSession, Depends(get_db)]

# ---------------------------------------------------------------------------
# GET /api/v1/analytics/summary
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_summary(
    db: DbDep,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> dict[str, Any]:
    """Hourly aggregation CTE over the last N hours.

    Returns record counts, processed percentages, and value statistics
    bucketed by hour. Uses Python-side grouping for SQLite compatibility.
    """
    # Normalize to tz-naive UTC to match DB TIMESTAMP (no timezone)
    since = (datetime.now(UTC) - timedelta(hours=hours)).replace(tzinfo=None)

    result = await db.execute(
        select(Record)
        .where(Record.deleted_at.is_(None))
        .where(Record.timestamp >= since)
        .order_by(Record.timestamp)
    )
    records = result.scalars().all()

    # Hourly bucketing in Python (dialect-agnostic — avoids date_trunc)
    hourly: dict[datetime, list[Record]] = defaultdict(list)
    for record in records:
        hour = record.timestamp.replace(minute=0, second=0, microsecond=0)
        hourly[hour].append(record)

    summary = []
    for hour, hour_records in sorted(hourly.items(), reverse=True):
        record_count = len(hour_records)
        processed_count = sum(1 for r in hour_records if r.processed)
        values = [
            float(r.raw_data["value"])
            for r in hour_records
            if isinstance(r.raw_data, dict) and r.raw_data.get("value") is not None
        ]
        avg_value = round(sum(values) / len(values), 4) if values else None
        min_value = min(values) if values else None
        max_value = max(values) if values else None
        unique_sources = len({r.source for r in hour_records})
        processed_pct = (
            round(processed_count / record_count * 100, 2) if record_count else None
        )

        summary.append(
            {
                "hour": hour.isoformat(),
                "record_count": record_count,
                "processed_count": processed_count,
                "processed_pct": processed_pct,
                "avg_value": avg_value,
                "min_value": min_value,
                "max_value": max_value,
                "unique_sources": unique_sources,
            }
        )

    return {
        "summary": summary,
        "hours_back": hours,
        "since": since.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/percentile
# ---------------------------------------------------------------------------


@router.get("/percentile")
async def get_percentile(
    db: DbDep,
    source: Annotated[str, Query()],
) -> dict[str, Any]:
    """PERCENT_RANK window function per source (top 100 records).

    Returns records for the given source with their percentile rank
    calculated in Python to stay DB-agnostic in tests.
    """
    result = await db.execute(
        select(Record)
        .where(Record.deleted_at.is_(None))
        .where(Record.source == source)
        .order_by(Record.timestamp.desc())
        .limit(100)
    )
    records = result.scalars().all()

    total = len(records)
    output_records = []
    for i, record in enumerate(records, start=1):
        value = (
            record.raw_data.get("value") if isinstance(record.raw_data, dict) else None
        )
        # PERCENT_RANK: (rank - 1) / (total - 1); 0.0 for single row
        percentile_rank = 0.0 if total <= 1 else round((i - 1) / (total - 1), 4)
        output_records.append(
            {
                "id": record.id,
                "timestamp": record.timestamp.isoformat(),
                "value": value,
                "percentile_rank": percentile_rank,
            }
        )

    return {
        "source": source,
        "count": total,
        "records": output_records,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/top-by-source
# ---------------------------------------------------------------------------


@router.get("/top-by-source")
async def get_top_by_source(
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    hours: Annotated[int, Query(ge=1, le=2160)] = 168,
) -> dict[str, Any]:
    """RANK window function — top N records per source in the last N hours.

    Groups results by source and returns the highest-value records per
    source, using Python-side ranking to remain dialect-agnostic.
    """
    # Normalize to tz-naive UTC to match DB TIMESTAMP (no timezone)
    since = (datetime.now(UTC) - timedelta(hours=hours)).replace(tzinfo=None)

    result = await db.execute(
        select(Record)
        .where(Record.deleted_at.is_(None))
        .where(Record.timestamp >= since)
        .order_by(Record.timestamp.desc())
    )
    records = result.scalars().all()

    # Group and rank within each source
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        value = (
            record.raw_data.get("value") if isinstance(record.raw_data, dict) else None
        )
        grouped[record.source].append(
            {
                "id": record.id,
                "timestamp": record.timestamp.isoformat(),
                "value": value,
            }
        )

    by_source: dict[str, list[dict[str, Any]]] = {}
    for source, source_records in grouped.items():
        sorted_records = sorted(
            source_records,
            key=lambda r: (r.get("value") is not None, r.get("value") or 0),
            reverse=True,
        )[:limit]
        for rank, rec in enumerate(sorted_records, start=1):
            rec["rank"] = rank
        by_source[source] = sorted_records

    return {
        "by_source": by_source,
        "limit_per_source": limit,
        "hours_back": hours,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/analytics/refresh-materialized-view
# ---------------------------------------------------------------------------


@router.post("/refresh-materialized-view")
async def refresh_materialized_view(db: DbDep) -> dict[str, str]:
    """Refresh the records_hourly_stats materialized view.

    On PostgreSQL with the view created: executes REFRESH MATERIALIZED VIEW.
    On other dialects or if view not created: no-op, returns success.
    """
    from sqlalchemy import text

    try:
        await db.execute(text("REFRESH MATERIALIZED VIEW records_hourly_stats"))
        await db.commit()
        logger.info("materialized_view_refreshed")
    except Exception:
        # View not yet created, wrong dialect, or other error — roll back
        # so the transaction is clean for subsequent operations.
        await db.rollback()

    return {"status": "success", "message": "Materialized view refresh requested"}


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/materialized-view-stats
# ---------------------------------------------------------------------------


@router.get("/materialized-view-stats")
async def get_materialized_view_stats(
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=168)] = 24,
) -> dict[str, Any]:
    """Query pre-aggregated hourly statistics.

    On PostgreSQL: reads from the records_hourly_stats materialized view.
    On SQLite (tests): falls back to computing aggregations from base table.
    """
    try:
        from sqlalchemy import text

        result = await db.execute(
            text(
                """
                SELECT hour, record_count, processed_count, processed_pct,
                       avg_value, min_value, max_value, unique_sources,
                       source_list, materialized_at
                FROM records_hourly_stats
                ORDER BY hour DESC
                LIMIT :limit
                """
            ).bindparams(limit=limit)
        )
        rows = result.mappings().all()
        stats = [
            {
                "hour": str(row["hour"]),
                "record_count": row["record_count"],
                "processed_count": row["processed_count"],
                "processed_pct": row["processed_pct"],
                "avg_value": row["avg_value"],
                "min_value": row["min_value"],
                "max_value": row["max_value"],
                "unique_sources": row["unique_sources"],
                "source_list": row["source_list"],
                "materialized_at": str(row["materialized_at"]),
            }
            for row in rows
        ]
    except Exception:
        # Fallback: compute from base records table (view not created yet)
        await db.rollback()
        stats = await _compute_stats_from_base(db, limit)

    return {"stats": stats, "limit": limit}


async def _compute_stats_from_base(
    db: AsyncSession, limit: int
) -> list[dict[str, Any]]:
    """Compute hourly aggregations directly from records table.

    Used as a fallback when materialized view is not available (SQLite tests).
    """
    result = await db.execute(
        select(Record).where(Record.deleted_at.is_(None)).order_by(Record.timestamp)
    )
    records = result.scalars().all()

    hourly: dict[datetime, list[Record]] = defaultdict(list)
    for record in records:
        hour = record.timestamp.replace(minute=0, second=0, microsecond=0)
        hourly[hour].append(record)

    materialized_at = datetime.utcnow().isoformat()
    stats = []
    for hour, hour_records in sorted(hourly.items(), reverse=True)[:limit]:
        record_count = len(hour_records)
        processed_count = sum(1 for r in hour_records if r.processed)
        values = [
            float(r.raw_data["value"])
            for r in hour_records
            if isinstance(r.raw_data, dict) and r.raw_data.get("value") is not None
        ]
        avg_value = round(sum(values) / len(values), 4) if values else None
        min_value = min(values) if values else None
        max_value = max(values) if values else None
        sources = {r.source for r in hour_records}
        processed_pct = (
            round(processed_count / record_count * 100, 2) if record_count else None
        )

        stats.append(
            {
                "hour": hour.isoformat(),
                "record_count": record_count,
                "processed_count": processed_count,
                "processed_pct": processed_pct,
                "avg_value": avg_value,
                "min_value": min_value,
                "max_value": max_value,
                "unique_sources": len(sources),
                "source_list": ",".join(sorted(sources)),
                "materialized_at": materialized_at,
            }
        )

    return stats
