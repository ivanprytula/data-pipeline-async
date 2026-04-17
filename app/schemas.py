"""Pydantic v2 schemas (same for both stacks)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.constants import (
    MAX_BATCH_SIZE,
    MIN_BATCH_SIZE,
    SOURCE_MAX_LENGTH,
    SOURCE_MIN_LENGTH,
    TAGS_MAX_COUNT,
)


class RecordRequest(BaseModel):
    source: str = Field(..., min_length=SOURCE_MIN_LENGTH, max_length=SOURCE_MAX_LENGTH)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="ISO 8601 timestamp (defaults to current UTC if omitted)",
    )
    data: dict[str, Any]
    tags: list[str] = Field(default_factory=list, max_length=TAGS_MAX_COUNT)

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

    @field_validator("source")
    @classmethod
    def source_not_localhost(cls, v: str) -> str:
        """Reject localhost, loopback, and wildcard addresses as invalid sources.

        Week 2 Milestone 5: Custom validation rule demonstrating domain constraints.
        Rejects:
        - 'localhost' (hostname)
        - '127.0.0.1' (IPv4 loopback)
        - '::1' (IPv6 loopback)
        - '0.0.0.0' (IPv4 wildcard, "any address")
        - '::' (IPv6 wildcard, "any address")
        """
        v_lower = v.lower()
        forbidden = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "::"}
        if v_lower in forbidden:
            raise ValueError(
                f"source cannot be a reserved address ({v}). "
                "Use actual hostname or IP instead."
            )
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
    records: list[RecordRequest] = Field(
        ..., min_length=MIN_BATCH_SIZE, max_length=MAX_BATCH_SIZE
    )


class PaginationMeta(BaseModel):
    total: int
    skip: int
    limit: int
    has_more: bool


class RecordListResponse(BaseModel):
    records: list[RecordResponse]
    pagination: PaginationMeta
