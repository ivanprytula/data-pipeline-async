"""ORM models (async stack — identical structure to sync, different Base)."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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


class Record(Base, TimestampMixin):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Record id={self.id} source={self.source!r}>"
