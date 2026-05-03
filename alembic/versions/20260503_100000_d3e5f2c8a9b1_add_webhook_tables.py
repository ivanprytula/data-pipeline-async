"""Add webhook tables for event-driven ingestion with audit trail.

Revision ID: d3e5f2c8a9b1
Revises: f4a9b2c7d8e1
Create Date: 2026-05-03 10:00:00.000000

Creates:
- webhook_sources: Registry of webhook integrations (Stripe, Segment, Zapier, etc.)
- webhook_events: Audit log of all webhook deliveries (JSONB payload, headers, status)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e5f2c8a9b1"
down_revision: Union[str, Sequence[str], None] = "f4a9b2c7d8e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create webhook_sources and webhook_events tables with indexes."""
    # Table 1: webhook_sources
    # Stores webhook integration metadata and signing key references
    op.create_table(
        "webhook_sources",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("signing_key_secret_name", sa.String(length=256), nullable=False),
        sa.Column("signing_algorithm", sa.String(length=32), nullable=False, server_default="HMAC-SHA256"),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_webhook_sources_name_active", "webhook_sources", ["name", "is_active"])

    # Table 2: webhook_events
    # Immutable audit log of all webhook deliveries
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("delivery_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("published_to_kafka", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("kafka_offset", sa.BigInteger(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'published', 'failed', 'replay_queued')",
            name="valid_webhook_event_status",
        ),
    )
    op.create_index("ix_webhook_events_source_created", "webhook_events", ["source", "created_at"])
    op.create_index("ix_webhook_events_delivery_id", "webhook_events", ["delivery_id"])
    op.create_index("ix_webhook_events_idempotency_key", "webhook_events", ["idempotency_key"])
    op.create_index("ix_webhook_events_status", "webhook_events", ["status"])

    # Seed initial webhook sources
    op.execute(
        """
        INSERT INTO webhook_sources (name, description, signing_key_secret_name, signing_algorithm, rate_limit_per_minute, is_active)
        VALUES
            ('stripe', 'Stripe payment events', 'data-zoo/webhook/stripe/signing-key', 'HMAC-SHA256', 100, TRUE),
            ('segment', 'Segment analytics events', 'data-zoo/webhook/segment/signing-key', 'HMAC-SHA256', 200, TRUE),
            ('zapier', 'Zapier webhook integration', 'data-zoo/webhook/zapier/signing-key', 'HMAC-SHA256', 50, TRUE)
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    """Drop webhook tables and indexes."""
    op.drop_index("ix_webhook_events_status", table_name="webhook_events")
    op.drop_index("ix_webhook_events_idempotency_key", table_name="webhook_events")
    op.drop_index("ix_webhook_events_delivery_id", table_name="webhook_events")
    op.drop_index("ix_webhook_events_source_created", table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index("ix_webhook_sources_name_active", table_name="webhook_sources")
    op.drop_table("webhook_sources")
