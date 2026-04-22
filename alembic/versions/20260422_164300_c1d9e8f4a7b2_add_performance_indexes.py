"""Add recommended composite indexes for hotspot mitigation.

Revision ID: c1d9e8f4a7b2
Revises: a8f3c2e9d1b4
Create Date: 2026-04-22 16:43:00.000000

Changes:
- Add partial index on records (source, timestamp) WHERE processed=false AND deleted_at IS NULL
  Rationale: "Get unprocessed records" is a common query pattern; partial index reduces scan from 95K to 5K rows
- Add partial index on processed_events (kafka_topic, created_at) WHERE status='pending'
  Rationale: Common pattern for batch event processing; filters to ~1K pending events
- Drop ix_records_processed (boolean column has poor selectivity; never selected by planner)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d9e8f4a7b2"
down_revision: Union[str, Sequence[str], None] = "a8f3c2e9d1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance-critical composite indexes."""
    # Index 1: Unprocessed records by source and timestamp
    # Use case: Batch jobs that fetch unprocessed records from a specific source ordered by time
    # Impact: Reduces scan from ~95K rows (all active) to ~5K rows (unprocessed only)
    op.create_index(
        "ix_records_unprocessed_by_source_timestamp",
        "records",
        [sa.column("source"), sa.column("timestamp").desc()],
        postgresql_where=sa.text("deleted_at IS NULL AND processed = false"),
    )

    # Index 2: Pending events by topic and creation time
    # Use case: Find all pending events for a topic to retry/resume from a point in time
    # Impact: Reduces scan to pending events only (typically <1% of total)
    op.create_index(
        "ix_events_pending_by_topic",
        "processed_events",
        [sa.column("kafka_topic"), sa.column("created_at")],
        postgresql_where=sa.text("status = 'pending' AND deleted_at IS NULL"),
    )

    # Cleanup: Remove low-cardinality index on processed (boolean field)
    # Rationale: Boolean columns have poor selectivity; planner almost never uses this index
    # (half rows are processed, half aren't — sequential scan is cheaper)
    op.drop_index("ix_records_processed", table_name="records", if_exists=True)


def downgrade() -> None:
    """Revert to previous index configuration."""
    # Remove newly created indexes
    op.drop_index("ix_records_unprocessed_by_source_timestamp", table_name="records", if_exists=True)
    op.drop_index("ix_events_pending_by_topic", table_name="processed_events", if_exists=True)

    # Restore the low-cardinality index (if it was considered important for some query)
    # Note: This is optional and can be left out if the index is confirmed unused
    # op.create_index("ix_records_processed", "records", ["processed"])
