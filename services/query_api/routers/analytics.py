"""Analytics read-only endpoints using advanced SQL patterns.

Features:
- CTE-based multi-step aggregations (summary)
- Window functions: PERCENT_RANK, RANK, ROW_NUMBER
- Materialized view queries with refresh
- Partitioned table range scans

Note: Database session is injected by main.py at router include time.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.query_api.dependencies import get_db


router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)


@router.get("/summary")
async def get_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = Query(24, ge=1, le=168, description="Hours of data to summarize"),
) -> dict:
    """Get aggregated summary using multi-step CTE.

    Returns: hour buckets with count, processed %, avg/min/max values, and unique sources.

    Query Pattern:
    1. Hourly bucketing: date_trunc('hour', timestamp)
    2. Aggregation: COUNT, FILTER (WHERE processed), MIN/MAX, array_agg
    3. Enrichment: Calculate processed percentage, format results

    For Phase 5 learning: demonstrates CTEs, aggregation functions, and window semantics.
    """
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours)

    query = text(
        """
        WITH recent_records AS (
            -- Step 1: Filter recent, non-deleted records
            SELECT
                date_trunc('hour', "timestamp")::TIMESTAMP AS hour,
                source,
                processed,
                COALESCE((raw_data->>'value')::NUMERIC, 0) AS value
            FROM records
            WHERE deleted_at IS NULL AND "timestamp" >= :since
        ),
        hourly_agg AS (
            -- Step 2: Aggregate per hour
            SELECT
                hour,
                COUNT(*) AS record_count,
                COUNT(*) FILTER (WHERE processed = true) AS processed_count,
                ROUND(AVG(value)::NUMERIC, 4) AS avg_value,
                MIN(value) AS min_value,
                MAX(value) AS max_value,
                COUNT(DISTINCT source) AS unique_sources
            FROM recent_records
            GROUP BY hour
        )
        -- Step 3: Enrich with calculated fields
        SELECT
            hour,
            record_count,
            processed_count,
            ROUND((processed_count::NUMERIC / NULLIF(record_count, 0) * 100)::NUMERIC, 2) AS processed_pct,
            avg_value,
            min_value,
            max_value,
            unique_sources
        FROM hourly_agg
        ORDER BY hour DESC
        """  # noqa: E501
    )

    result = await db.execute(query, {"since": since})
    rows = result.fetchall()

    return {
        "hours_back": hours,
        "since": since.isoformat(),
        "summary": [
            {
                "hour": row[0].isoformat(),
                "record_count": row[1],
                "processed_count": row[2],
                "processed_pct": float(row[3]) if row[3] else 0,
                "avg_value": float(row[4]) if row[4] else None,
                "min_value": float(row[5]) if row[5] else None,
                "max_value": float(row[6]) if row[6] else None,
                "unique_sources": row[7],
            }
            for row in rows
        ],
    }


@router.get("/percentile")
async def get_percentile(
    db: Annotated[AsyncSession, Depends(get_db)],
    source: str = Query(..., description="Filter by source"),
) -> dict:
    """Percentile rankings using PERCENT_RANK window function.

    Returns: records with their percentile rank within the source.

    Query Pattern:
    - PERCENT_RANK() OVER (PARTITION BY source ORDER BY value DESC)
    - Returns 0.0 (lowest) to 1.0 (highest)

    Typical use: Find records in top 10% of values for a given source.
    """
    query = text(
        """
        SELECT
            id,
            source,
            "timestamp",
            COALESCE((raw_data->>'value')::NUMERIC, 0) AS value,
            processed,
            ROUND(
                (PERCENT_RANK() OVER (PARTITION BY source ORDER BY COALESCE((raw_data->>'value')::NUMERIC, 0) DESC))::NUMERIC,
                4
            ) AS percentile_rank
        FROM records
        WHERE deleted_at IS NULL AND source = :source
        ORDER BY percentile_rank ASC
        LIMIT 100
        """  # noqa: E501
    )

    result = await db.execute(query, {"source": source})
    rows = result.fetchall()

    return {
        "source": source,
        "count": len(rows),
        "records": [
            {
                "id": row[0],
                "source": row[1],
                "timestamp": row[2].isoformat(),
                "value": float(row[3]) if row[3] else None,
                "processed": row[4],
                "percentile_rank": float(row[5]),
            }
            for row in rows
        ],
    }


@router.get("/top-by-source")
async def get_top_by_source(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(5, ge=1, le=50, description="Top N per source"),
    hours: int = Query(168, ge=1, le=2160, description="Hours of data to include"),
) -> dict:
    """Top N records per source using RANK window function.

    Returns: ranked records (1st, 2nd, 3rd, etc.) within each source, filtered by recency.

    Query Pattern:
    - RANK() OVER (PARTITION BY source ORDER BY value DESC)
    - RANK() is dense; matches include ties
    - Compared to ROW_NUMBER which always increments

    Typical use: Dashboard showing "Top records per data source this week".
    """
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours)

    query = text(
        """
        WITH ranked_records AS (
            SELECT
                id,
                source,
                "timestamp",
                COALESCE((raw_data->>'value')::NUMERIC, 0) AS value,
                processed,
                RANK() OVER (PARTITION BY source ORDER BY COALESCE((raw_data->>'value')::NUMERIC, 0) DESC) AS rank
            FROM records
            WHERE deleted_at IS NULL AND "timestamp" >= :since
        )
        SELECT * FROM ranked_records
        WHERE rank <= :limit
        ORDER BY source, rank
        """  # noqa: E501
    )

    result = await db.execute(query, {"since": since, "limit": limit})
    rows = result.fetchall()

    # Group by source for hierarchical response
    by_source: dict[str, list] = {}
    for row in rows:
        source = row[1]
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(
            {
                "id": row[0],
                "timestamp": row[2].isoformat(),
                "value": float(row[3]) if row[3] else None,
                "processed": row[4],
                "rank": row[5],
            }
        )

    return {
        "limit_per_source": limit,
        "hours_back": hours,
        "since": since.isoformat(),
        "by_source": by_source,
    }


@router.post("/refresh-materialized-view")
async def refresh_materialized_view(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Manually refresh the materialized view.

    In production: Run this periodically via APScheduler or Kubernetes CronJob.
    Example cron: Every 1 hour at the 5-minute mark.

    Note: REFRESH MATERIALIZED VIEW CONCURRENTLY requires a unique index.
    For now, using blocking refresh (locks writers briefly).
    """
    try:
        # Blocking refresh (simple, but locks writers)
        await db.execute(text("REFRESH MATERIALIZED VIEW records_hourly_stats"))
        await db.commit()

        return {"status": "success", "message": "Materialized view refreshed"}
    except Exception:
        await db.rollback()
        logger.exception("Failed to refresh materialized view")
        return {
            "status": "error",
            "message": "Failed to refresh materialized view",
        }


@router.get("/materialized-view-stats")
async def get_materialized_view_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(24, ge=1, le=168, description="Number of hour buckets"),
) -> dict:
    """Query the materialized view directly.

    Pre-aggregated hourly statistics. Fast reads, eventual consistency.
    """
    query = text(
        """
        SELECT
            hour,
            record_count,
            processed_count,
            processed_pct,
            avg_value,
            min_value,
            max_value,
            unique_sources,
            materialized_at
        FROM records_hourly_stats
        ORDER BY hour DESC
        LIMIT :limit
        """
    )

    result = await db.execute(query, {"limit": limit})
    rows = result.fetchall()

    return {
        "limit": limit,
        "count": len(rows),
        "stats": [
            {
                "hour": row[0].isoformat(),
                "record_count": row[1],
                "processed_count": row[2],
                "processed_pct": float(row[3]) if row[3] else 0,
                "avg_value": float(row[4]) if row[4] else None,
                "min_value": float(row[5]) if row[5] else None,
                "max_value": float(row[6]) if row[6] else None,
                "unique_sources": row[7],
                "materialized_at": row[8].isoformat() if row[8] else None,
            }
            for row in rows
        ],
    }
