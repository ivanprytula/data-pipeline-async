"""ORM models (async stack — identical structure to sync, different Base)."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ingestor.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    """Adds created_at, updated_at, and deleted_at to any model.

    - created_at: set once on INSERT, never changes
    - updated_at: set on INSERT and refreshed on every UPDATE
    - deleted_at: NULL until soft-deleted; non-NULL means logically deleted
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProcessedEvent(Base, TimestampMixin):
    """Tracks consumed Kafka events with processing state and idempotency.

    Industry pattern: Event persistence with status tracking enables:
    - Replay from failures (track offset)
    - Deduplication (idempotency_key prevents double-processing)
    - DLQ routing (failed events send to dead_letter_queue)
    - Audit trail (complete lifecycle visible in database)
    """

    __tablename__ = "processed_events"
    __table_args__ = (
        Index("ix_events_idempotency_key", "idempotency_key", unique=True),
        Index("ix_events_status", "status"),
        Index("ix_events_kafka_offset", "kafka_offset"),
        Index("ix_events_dead_letter_queue", "dead_letter_queue"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Kafka metadata
    kafka_topic: Mapped[str] = mapped_column(String(255), nullable=False)
    kafka_partition: Mapped[int] = mapped_column(Integer, nullable=False)
    kafka_offset: Mapped[int] = mapped_column(Integer, nullable=False)

    # Event deduplication (industry standard: idempotency keys prevent double-processing)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Event payload storage
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., "record.created"
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Processing state tracking
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )  # pending → processing → completed | failed | dead_letter
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Error tracking for failed events
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Dead letter queue indicator
    dead_letter_queue: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    dlq_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps from TimestampMixin: created_at, updated_at, deleted_at
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Record(Base, TimestampMixin):
    __tablename__ = "records"
    __table_args__ = (
        Index(
            "ix_records_active_source",
            "source",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_records_timestamp", "timestamp"),
        Index("ix_records_processed", "processed"),
        UniqueConstraint("source", "timestamp", name="uq_records_source_timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Record id={self.id} source={self.source!r}>"


class User(Base, TimestampMixin):
    """Basic user model for authentication and RBAC role assignment.

    This is intentionally minimal for the current pillar scope:
    - identity fields (username, email)
    - credential field (password_hash)
    - coarse role field (viewer/writer/admin)
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_username", "username", unique=True),
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_role", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="viewer", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"
