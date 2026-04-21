"""Add materialized views and partitioned table for analytics.

Revision ID: a8f3c2e9d1b4
Revises: b770f07991cf
Create Date: 2026-04-21 18:00:01.000000

Changes:
- Materialized view: records_hourly_stats (hourly aggregations with CTEs)
- Partitioned table: records_archive (monthly range partitioning)
- pgvector extension (for vector similarity comparison alongside Qdrant)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8f3c2e9d1b4"
down_revision: Union[str, Sequence[str], None] = "b770f07991cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with materialized views, partitioning, and extensions."""
    # Create pgvector extension (for comparison with Qdrant in Phase 5)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create materialized view: records_hourly_stats
    # Pattern: Multi-step CTE aggregation (hour-level stats for dashboard)
    op.execute(
        """
        CREATE MATERIALIZED VIEW records_hourly_stats AS
        WITH hourly_records AS (
            -- Step 1: Bucket records by hour, exclude deleted/unprocessed
            SELECT
                date_trunc('hour', "timestamp") AS hour,
                source,
                processed,
                raw_data,
                tags
            FROM records
            WHERE deleted_at IS NULL
        ),
        hour_stats AS (
            -- Step 2: Aggregate metrics per hour
            SELECT
                hour,
                COUNT(*) AS record_count,
                COUNT(*) FILTER (WHERE processed = true) AS processed_count,
                ROUND(
                    AVG(COALESCE((raw_data->>'value')::NUMERIC, 0))::NUMERIC,
                    4
                ) AS avg_value,
                MIN(COALESCE((raw_data->>'value')::NUMERIC, NULL)) AS min_value,
                MAX(COALESCE((raw_data->>'value')::NUMERIC, NULL)) AS max_value,
                COUNT(DISTINCT source) AS unique_sources,
                array_agg(DISTINCT source ORDER BY source) AS source_list
            FROM hourly_records
            GROUP BY hour
        )
        -- Step 3: Final enrichment
        SELECT
            hour,
            record_count,
            processed_count,
            ROUND(
                (processed_count::NUMERIC / NULLIF(record_count, 0) * 100)::NUMERIC,
                2
            ) AS processed_pct,
            avg_value,
            min_value,
            max_value,
            unique_sources,
            source_list,
            NOW() AS materialized_at
        FROM hour_stats
        ORDER BY hour DESC;
        """
    )

    # Index on materialized view for fast lookups
    op.execute("CREATE INDEX idx_records_hourly_stats_hour ON records_hourly_stats (hour DESC)")

    # Create partitioned table: records_archive
    # Pattern: Range partitioning by month for old records (3+ months)
    # Note: PostgreSQL 17 requires PRIMARY KEY and UNIQUE constraints to include partitioning column
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS records_archive (
            id INTEGER NOT NULL,
            source VARCHAR(255) NOT NULL,
            "timestamp" TIMESTAMP NOT NULL,
            raw_data JSON NOT NULL,
            tags JSON NOT NULL DEFAULT '[]'::JSON,
            processed BOOLEAN NOT NULL DEFAULT false,
            processed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP,
            deleted_at TIMESTAMP,
            PRIMARY KEY (id, "timestamp"),
            CONSTRAINT uq_archive_source_timestamp UNIQUE (source, "timestamp")
        ) PARTITION BY RANGE ("timestamp");
        """
    )

    # Create partitions for last 12 months (lazy evaluation for future months)
    # Example: 2025-04, 2025-05, 2025-06, ..., 2026-04
    partition_months = [
        ("2025-04", "2025-05"),
        ("2025-05", "2025-06"),
        ("2025-06", "2025-07"),
        ("2025-07", "2025-08"),
        ("2025-08", "2025-09"),
        ("2025-09", "2025-10"),
        ("2025-10", "2025-11"),
        ("2025-11", "2025-12"),
        ("2025-12", "2026-01"),
        ("2026-01", "2026-02"),
        ("2026-02", "2026-03"),
        ("2026-03", "2026-04"),
        ("2026-04", "2026-05"),
    ]

    for start_month, end_month in partition_months:
        partition_name = f"records_archive_{start_month.replace('-', '')}"
        start_date = f"{start_month}-01"
        end_date = f"{end_month}-01"
        op.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF records_archive
            FOR VALUES FROM ('{start_date}'::TIMESTAMP) TO ('{end_date}'::TIMESTAMP);
            """
        )
        # Index on timestamp for range queries
        op.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{partition_name}_timestamp ON {partition_name} (timestamp DESC)"
        )

    # Index on source for lookups
    op.execute("CREATE INDEX idx_records_archive_source ON records_archive (source)")


def downgrade() -> None:
    """Downgrade schema: remove views, partitions, and extensions."""
    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS records_hourly_stats CASCADE")

    # Drop partitioned table (and all partitions)
    op.execute("DROP TABLE IF EXISTS records_archive CASCADE")

    # Drop extension
    op.execute("DROP EXTENSION IF EXISTS vector")
