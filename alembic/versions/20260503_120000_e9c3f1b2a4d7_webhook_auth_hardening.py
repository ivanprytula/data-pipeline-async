"""Webhook auth hardening: API key lifecycle, key versioning, per-source retry config.

Revision ID: e9c3f1b2a4d7
Revises: d3e5f2c8a9b1
Create Date: 2026-05-03 12:00:00.000000

Changes:
- webhook_sources: add api_key_hash (Argon2), signing_key_version, retry_config JSONB
- webhook_events: add signing_key_version (tracks which key validated), next_retry_at
- New table webhook_api_keys: per-source API key lifecycle (create/revoke/rotate)
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e9c3f1b2a4d7"
down_revision: str | Sequence[str] | None = "d3e5f2c8a9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add webhook auth hardening columns and api_keys table."""
    # ── webhook_sources: signing key versioning + retry config ────────────────
    op.add_column(
        "webhook_sources",
        sa.Column(
            "signing_key_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Current signing key version. Increments on each rotation.",
        ),
    )
    op.add_column(
        "webhook_sources",
        sa.Column(
            "deprecated_key_version",
            sa.Integer(),
            nullable=True,
            comment="Previous key version kept alive for 7-day grace period after rotation.",
        ),
    )
    op.add_column(
        "webhook_sources",
        sa.Column(
            "key_deprecated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp when the deprecated key was superseded. "
                "Grace period expires 7 days after this."
            ),
        ),
    )
    op.add_column(
        "webhook_sources",
        sa.Column(
            "retry_config",
            sa.JSON(),
            nullable=False,
            server_default=(
                '{"max_attempts": 5, "backoff_base_seconds": 30, '
                '"backoff_multiplier": 2}'
            ),
            comment="Per-source retry backoff config. Overrides global defaults.",
        ),
    )

    # ── webhook_events: key version tracking + next retry timestamp ───────────
    op.add_column(
        "webhook_events",
        sa.Column(
            "signing_key_version",
            sa.Integer(),
            nullable=True,
            comment="Key version that validated this event. NULL for events before Phase 13.3.",
        ),
    )
    op.add_column(
        "webhook_events",
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Next scheduled retry timestamp. NULL for events not pending retry.",
        ),
    )
    op.create_index(
        "ix_webhook_events_next_retry_at",
        "webhook_events",
        ["next_retry_at"],
        postgresql_where=sa.text("next_retry_at IS NOT NULL AND status = 'replay_queued'"),
    )

    # ── webhook_api_keys: per-source API key lifecycle ─────────────────────────
    op.create_table(
        "webhook_api_keys",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("webhook_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "key_hash",
            sa.String(length=256),
            nullable=False,
            comment="Argon2id hash of the API key. Plaintext is never stored.",
        ),
        sa.Column(
            "key_prefix",
            sa.String(length=16),
            nullable=False,
            comment="First 8 chars of raw key for identification in admin UI (e.g., 'wk_abc123').",
        ),
        sa.Column(
            "label",
            sa.String(length=128),
            nullable=True,
            comment="Optional human-readable label (e.g., 'production', 'ci-testing').",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of revocation. NULL for active keys.",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful authentication. Updated on each valid request.",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webhook_api_keys_source_active",
        "webhook_api_keys",
        ["source_id", "is_active"],
    )
    op.create_index(
        "ix_webhook_api_keys_key_prefix",
        "webhook_api_keys",
        ["key_prefix"],
    )


def downgrade() -> None:
    """Remove webhook auth hardening additions."""
    op.drop_index("ix_webhook_api_keys_key_prefix", table_name="webhook_api_keys")
    op.drop_index("ix_webhook_api_keys_source_active", table_name="webhook_api_keys")
    op.drop_table("webhook_api_keys")

    op.drop_index("ix_webhook_events_next_retry_at", table_name="webhook_events")
    op.drop_column("webhook_events", "next_retry_at")
    op.drop_column("webhook_events", "signing_key_version")

    op.drop_column("webhook_sources", "retry_config")
    op.drop_column("webhook_sources", "key_deprecated_at")
    op.drop_column("webhook_sources", "deprecated_key_version")
    op.drop_column("webhook_sources", "signing_key_version")
