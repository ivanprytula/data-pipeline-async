"""SQLAlchemy ORM models for the webhook service.

Uses SQLAlchemy 2.0 Mapped[T] / mapped_column() style exclusively.
Base is imported from the shared database module so all models share
the same metadata (used by Alembic for migrations at the repo root).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Adds created_at and updated_at to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=True
    )


class WebhookSource(Base, TimestampMixin):
    """Registry of webhook integrations (Stripe, Segment, Zapier, etc.).

    Stores metadata about webhook sources, signing key references, and rate limits.
    Each source represents an external service that sends webhook events.
    """

    __tablename__ = "webhook_sources"
    __table_args__ = (Index("ix_webhook_sources_name_active", "name", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signing_key_secret_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    signing_algorithm: Mapped[str] = mapped_column(
        String(32), default="HMAC-SHA256", nullable=False
    )
    rate_limit_per_minute: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<WebhookSource id={self.id} name={self.name!r} active={self.is_active}>"
        )


class WebhookEvent(Base, TimestampMixin):
    """Immutable audit log of all webhook deliveries.

    Tracks every webhook delivery with payload, headers, signature validation,
    processing attempts, and Kafka publish status. Enables deduplication,
    replay, and complete audit trail.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        Index("ix_webhook_events_source_created", "source", "created_at"),
        Index("ix_webhook_events_delivery_id", "delivery_id"),
        Index("ix_webhook_events_idempotency_key", "idempotency_key"),
        Index("ix_webhook_events_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    delivery_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(256), nullable=True, unique=True
    )
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    headers: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_to_kafka: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    kafka_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<WebhookEvent id={self.id} source={self.source!r} "
            f"status={self.status!r} delivery_id={self.delivery_id[:8]}...>"
        )
