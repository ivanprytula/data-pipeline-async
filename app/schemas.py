"""Pydantic v2 schemas (same for both stacks)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RecordRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=255)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="ISO 8601 timestamp (defaults to current UTC if omitted)",
    )
    data: dict[str, Any]
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v: datetime) -> datetime:
        """Strip timezone info for consistent storage (naive UTC)."""
        if isinstance(v, datetime) and v.tzinfo is not None:
            v = v.replace(tzinfo=None)
        return v

    @field_validator("timestamp")
    @classmethod
    def not_in_future(cls, v: datetime) -> datetime:
        """Reject timestamps after current time."""
        # Normalize to tz-naive for safe comparison
        if isinstance(v, datetime) and v.tzinfo is not None:
            v = v.replace(tzinfo=None)
        if v > datetime.now(UTC).replace(tzinfo=None):
            raise ValueError("timestamp cannot be in the future")
        return v

    @field_validator("tags")
    @classmethod
    def lowercase_tags(cls, v: list[str]) -> list[str]:
        return [t.lower() for t in v]


class RecordResponse(BaseModel):
    id: int
    source: str
    timestamp: datetime
    raw_data: dict[str, Any]
    tags: list[str]
    processed: bool
    # audit columns from TimestampMixin
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None

    model_config = {"from_attributes": True}


class BatchRecordsRequest(BaseModel):
    records: list[RecordRequest] = Field(..., min_length=1, max_length=1000)


class PaginationMeta(BaseModel):
    total: int
    skip: int
    limit: int
    has_more: bool


class RecordListResponse(BaseModel):
    records: list[RecordResponse]
    pagination: PaginationMeta
