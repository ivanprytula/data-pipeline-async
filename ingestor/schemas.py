"""Pydantic v2 schemas (same for both stacks)."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from ingestor.constants import (
    ENRICH_MAX_IDS,
    ENRICH_MIN_IDS,
    MAX_BATCH_SIZE,
    MIN_BATCH_SIZE,
    SOURCE_MAX_LENGTH,
    SOURCE_MIN_LENGTH,
    TAGS_MAX_COUNT,
    UPSERT_MODE_IDEMPOTENT,
    UPSERT_MODE_STRICT,
    VECTOR_SEARCH_DEFAULT_TOP_K,
    VECTOR_SEARCH_MAX_RECORD_IDS,
    VECTOR_SEARCH_MAX_TOP_K,
    VECTOR_SEARCH_MIN_RECORD_IDS,
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


class UpdateRecordRequest(BaseModel):
    """Partial update schema — all fields are optional."""

    source: str | None = Field(
        None, min_length=SOURCE_MIN_LENGTH, max_length=SOURCE_MAX_LENGTH
    )
    timestamp: datetime | None = None
    data: dict[str, Any] | None = None
    tags: list[str] | None = Field(None, max_length=TAGS_MAX_COUNT)

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v: datetime | None) -> datetime | None:
        """Strip timezone info for consistent storage (naive UTC)."""
        if isinstance(v, datetime) and v.tzinfo is not None:
            v = v.replace(tzinfo=None)
        return v

    @field_validator("timestamp")
    @classmethod
    def not_in_future(cls, v: datetime | None) -> datetime | None:
        """Reject timestamps after current time."""
        if v is None:
            return v
        # Normalize to tz-naive for safe comparison
        if isinstance(v, datetime) and v.tzinfo is not None:
            v = v.replace(tzinfo=None)
        if v > datetime.now(UTC).replace(tzinfo=None):
            raise ValueError("timestamp cannot be in the future")
        return v

    @field_validator("source")
    @classmethod
    def source_not_localhost(cls, v: str | None) -> str | None:
        """Reject localhost, loopback, and wildcard addresses as invalid sources."""
        if v is None:
            return v
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
    def lowercase_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
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


class EnrichRequest(BaseModel):
    """Request payload for the concurrent enrichment endpoint."""

    record_ids: list[int] = Field(
        ...,
        min_length=ENRICH_MIN_IDS,
        max_length=ENRICH_MAX_IDS,
        description=f"Record IDs to enrich (1–{ENRICH_MAX_IDS} IDs per call)",
    )


class EnrichedRecord(BaseModel):
    """Single enrichment result — the original record plus external metadata."""

    record_id: int
    source: str
    external_title: str | None = None
    external_body: str | None = None
    enriched: bool
    error: str | None = None

    model_config = {"from_attributes": False}


class EnrichResponse(BaseModel):
    """Response from POST /api/v2/records/enrich."""

    enriched_count: int
    failed_count: int
    duration_ms: float
    results: list[EnrichedRecord]


# ---------------------------------------------------------------------------
# Idempotent upsert schemas (Step 9)
# ---------------------------------------------------------------------------


class UpsertRequest(RecordRequest):
    """Request payload for POST /api/v2/records/upsert.

    Inherits all fields and validators from RecordRequest.
    The (source, timestamp) pair is the idempotency key — a second upsert
    with the same pair returns the existing record rather than creating a duplicate.
    """


class UpsertResponse(BaseModel):
    """Response from POST /api/v2/records/upsert.

    Attributes:
        record: The record (newly created or pre-existing).
        created: True if a new row was inserted; False if an existing row was returned.
        mode: The conflict resolution mode used ("idempotent" or "strict").
    """

    record: RecordResponse
    created: bool
    mode: str = UPSERT_MODE_IDEMPOTENT

    model_config = {"from_attributes": False}


class UpsertMode:
    """Valid values for the upsert ?mode= query parameter."""

    IDEMPOTENT: str = UPSERT_MODE_IDEMPOTENT
    """201 on create, 200 on conflict — safe to retry."""

    STRICT: str = UPSERT_MODE_STRICT
    """201 on create, 409 on conflict — explicit error on duplicate."""


# ---------------------------------------------------------------------------
# Cursor-based pagination schemas (high-load pagination)
# ---------------------------------------------------------------------------


class CursorPaginationResponse(BaseModel):
    """Response for cursor-based pagination.

    Attributes:
        records: List of records in this page.
        next_cursor: Opaque cursor for the next page (None if no more results).
        has_more: True if more records exist beyond this page.
        limit: The limit used for this request.
    """

    records: list[RecordResponse]
    next_cursor: str | None = None
    has_more: bool = False
    limit: int


# ---------------------------------------------------------------------------
# Batch create response schema
# ---------------------------------------------------------------------------


class BatchCreateResponse(BaseModel):
    """Response from POST /api/v1/records/batch.

    Attributes:
        created: Number of records successfully created.
        impl: The batch implementation used ("optimized" or "naive").
    """

    created: int
    impl: str


# ---------------------------------------------------------------------------
# Session/login response schema
# ---------------------------------------------------------------------------


class SessionResponse(BaseModel):
    """Response from POST /api/v1/records/auth/login (session-based auth).

    Attributes:
        session_id: Unique session identifier for this user.
        message: Confirmation message.
    """

    session_id: str
    message: str


# ---------------------------------------------------------------------------
# Scraper response schema (Phase 2)
# ---------------------------------------------------------------------------


class ScrapeResponse(BaseModel):
    """Response from POST /api/v1/scrape/{source}.

    Attributes:
        source: Scraper source identifier used (e.g., 'hn', 'jsonplaceholder').
        scraped: Number of items returned by the scraper.
        stored: Number of items successfully persisted to MongoDB.
    """

    source: str
    scraped: int
    stored: int


# ---------------------------------------------------------------------------
# Background processing schemas (Pillar 5)
# ---------------------------------------------------------------------------


class BackgroundBatchSubmitResponse(BaseModel):
    """Response from background batch ingestion submission endpoint."""

    task_id: str
    status: str
    batch_size: int
    queued_at: datetime


class BackgroundTaskStatusResponse(BaseModel):
    """Status response for a submitted background task."""

    task_id: str
    status: str
    batch_size: int
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Notifications schemas (Pillar 8)
# ---------------------------------------------------------------------------


class NotificationTestRequest(BaseModel):
    """Request payload for notification test endpoint."""

    message: str = Field(..., min_length=1, max_length=2000)
    severity: str = Field(default="info")
    event: str = Field(default="notification_test")
    channels: list[Literal["slack", "telegram", "webhook", "email"]] | None = None


class NotificationDispatchResult(BaseModel):
    """One channel dispatch result for notification test endpoint."""

    channel: str
    status: str
    detail: str


class NotificationTestResponse(BaseModel):
    """Response payload for notification test endpoint."""

    event: str
    severity: str
    sent: int
    failed: int
    results: list[NotificationDispatchResult] = Field(default_factory=list)
    detail: str | None = None


# ---------------------------------------------------------------------------
# Vector search schemas (Pillar 9)
# ---------------------------------------------------------------------------


class VectorSearchIndexRequest(BaseModel):
    """Request payload for indexing records into the AI gateway collection."""

    record_ids: list[int] = Field(
        ...,
        min_length=VECTOR_SEARCH_MIN_RECORD_IDS,
        max_length=VECTOR_SEARCH_MAX_RECORD_IDS,
        description="Record IDs to embed and index into the vector collection.",
    )
    collection: str | None = Field(
        default=None,
        description="Optional AI gateway collection override.",
    )


class VectorSearchIndexResponse(BaseModel):
    """Response from indexing records into the AI gateway."""

    requested_count: int
    indexed_count: int
    missing_record_ids: list[int] = Field(default_factory=list)
    collection: str


class VectorSearchReindexRecentRequest(BaseModel):
    """Request payload for indexing a recent window of active records."""

    source: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Optional source filter for recent records.",
    )
    limit: int = Field(
        default=VECTOR_SEARCH_MAX_RECORD_IDS,
        ge=1,
        le=VECTOR_SEARCH_MAX_RECORD_IDS,
        description="Maximum number of recent records to index.",
    )
    collection: str | None = Field(
        default=None,
        description="Optional AI gateway collection override.",
    )


class VectorSearchQueryRequest(BaseModel):
    """Request payload for semantic search over indexed records."""

    query: str = Field(..., min_length=1, description="Semantic search query text.")
    top_k: int = Field(
        default=VECTOR_SEARCH_DEFAULT_TOP_K,
        ge=1,
        le=VECTOR_SEARCH_MAX_TOP_K,
        description="Maximum number of nearest-neighbour matches to return.",
    )
    collection: str | None = Field(
        default=None,
        description="Optional AI gateway collection override.",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata filters forwarded to the AI gateway.",
    )


class VectorSearchResult(BaseModel):
    """One semantic-search match returned by the AI gateway."""

    id: int
    score: float
    metadata: dict[str, Any]


class VectorSearchQueryResponse(BaseModel):
    """Semantic-search response for indexed records."""

    results: list[VectorSearchResult]
    count: int
    query: str
    collection: str


class VectorSearchHealthResponse(BaseModel):
    """Health status of the AI gateway bridge used by Pillar 9."""

    status: str
    ai_gateway_connected: bool
    collection: str
