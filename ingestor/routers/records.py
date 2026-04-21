"""Records resource — all CRUD routes."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ingestor import cache, events
from ingestor.auth import create_session, verify_bearer_token, verify_session
from ingestor.constants import (
    API_V1_PREFIX,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    V1_RATE_LIMIT,
)
from ingestor.crud import (
    create_record as create_record_op,
)
from ingestor.crud import (
    create_records_batch as create_records_batch_op,
)
from ingestor.crud import (
    create_records_batch_naive as create_records_batch_naive_op,
)
from ingestor.crud import (
    delete_record as delete_record_op,
)
from ingestor.crud import (
    get_record as get_record_op,
)
from ingestor.crud import (
    get_records,
    mark_processed,
    soft_delete_record,
    update_record,
)
from ingestor.database import get_db
from ingestor.metrics import (
    batch_size_histogram,
    cache_hits_total,
    cache_misses_total,
    records_created_total,
)
from ingestor.rate_limiting import limiter
from ingestor.schemas import (
    BatchCreateResponse,
    BatchRecordsRequest,
    PaginationMeta,
    RecordListResponse,
    RecordRequest,
    RecordResponse,
    SessionResponse,
    UpdateRecordRequest,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{API_V1_PREFIX}/records", tags=["records"])

type DbDep = Annotated[AsyncSession, Depends(get_db)]
type SessionDep = Annotated[dict[str, Any], Depends(verify_session)]
type BearerTokenDep = Annotated[str, Depends(verify_bearer_token)]


# ---------------------------------------------------------------------------
# Records — single create
# ---------------------------------------------------------------------------
@router.post(
    "",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(V1_RATE_LIMIT)
async def create_record(
    request: Request,
    body: RecordRequest,
    db: DbDep,
) -> RecordResponse:
    """Create a single record.

    Logs are automatically tagged with correlation ID.
    Rate limit: 1000/minute per IP.
    """
    record = await create_record_op(db, body)
    records_created_total.labels(endpoint="single").inc()
    # Publish event after successful DB write (Observer pattern — fail-open)
    await events.publish_record_created(
        record_id=record.id,
        payload={"source": record.source},
    )
    return RecordResponse.model_validate(record)


# ---------------------------------------------------------------------------
@router.post(
    "/batch",
    response_model=BatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    description=(
        "Bulk-create records.\n\n"
        "**`?impl` query parameter** — internal implementation toggle:\n"
        "- `optimized` *(default)* — single `INSERT … RETURNING` round-trip\n"
        "- `naive` — `add_all` + N individual `REFRESH` calls (N+1 queries)\n\n"
        "Both return identical JSON. The difference is only observable as latency "
        "(use `?impl=naive` vs `?impl=optimized` with a large batch to feel it).\n\n"
        "This pattern — same contract, swappable internals — mirrors how "
        "feature flags and A/B performance experiments work in production."
    ),
)
async def create_records_batch(
    body: BatchRecordsRequest,
    db: DbDep,
    impl: str = Query(
        default="optimized",
        pattern="^(optimized|naive)$",
        description="Batch insert implementation: 'optimized' (INSERT RETURNING) or 'naive' (add_all + N refreshes).",  # noqa: E501
    ),
) -> BatchCreateResponse:
    """Create multiple records in batch.

    The `?impl=` parameter selects the internal database strategy without
    changing the response contract — identical JSON either way.
    """
    impl_fn = (
        create_records_batch_op
        if impl == "optimized"
        else create_records_batch_naive_op
    )
    logger.info("batch_create", extra={"count": len(body.records), "impl": impl})
    records = await impl_fn(db, body.records)
    batch_size_histogram.observe(len(records))
    records_created_total.labels(endpoint="batch").inc(len(records))
    logger.info("batch_created", extra={"count": len(records), "impl": impl})
    return BatchCreateResponse(created=len(records), impl=impl)


# ---------------------------------------------------------------------------
# Records — list with pagination
# ---------------------------------------------------------------------------
@router.get("", response_model=RecordListResponse)
async def list_records(
    db: DbDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    source: str | None = None,
) -> RecordListResponse:
    """List records with pagination and optional filtering by source."""
    records, total = await get_records(db, skip, limit, source)
    return RecordListResponse(
        records=[RecordResponse.model_validate(r) for r in records],
        pagination=PaginationMeta(
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + limit) < total,
        ),
    )


# ---------------------------------------------------------------------------
# Records — get by ID
# ---------------------------------------------------------------------------
@router.get(
    "/{record_id}",
    response_model=RecordResponse,
)
async def get_record(record_id: int, db: DbDep) -> RecordResponse:
    """Retrieve a single record by ID.

    Check cache first (Redis); on miss, fetch from DB and cache for 1 hour.
    Redis connection errors are transparent (fail-open).
    """
    # Try cache first
    cached_record = await cache.get_record(record_id)
    if cached_record is not None:
        cache_hits_total.labels(operation="get").inc()
        return cached_record

    # Cache miss: fetch from DB
    record = await get_record_op(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )

    # Store in cache for future hits
    response = RecordResponse.model_validate(record)
    await cache.set_record(record_id, response)
    cache_misses_total.labels(operation="get").inc()
    return response


# ---------------------------------------------------------------------------
# Records — update by ID (partial)
# ---------------------------------------------------------------------------
@router.patch(
    "/{record_id}",
    response_model=RecordResponse,
)
async def update_record_endpoint(
    record_id: int, body: UpdateRecordRequest, db: DbDep
) -> RecordResponse:
    """Update a record with provided fields (partial update).

    All fields are optional. Only provided fields are updated; others are
    left unchanged.

    Example (update source and tags):
    ```json
    {"source": "new-source", "tags": ["updated", "tags"]}
    ```
    """
    record = await update_record(db, record_id, body)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return RecordResponse.model_validate(record)


# ---------------------------------------------------------------------------
# Records — mark as processed
# ---------------------------------------------------------------------------
@router.patch(
    "/{record_id}/process",
    response_model=RecordResponse,
)
async def process_record(record_id: int, db: DbDep) -> RecordResponse:
    """Mark a record as processed.

    Invalidates any cached version so next GET reflects updated state.
    """
    record = await mark_processed(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    # Invalidate cache so next read gets fresh data
    await cache.invalidate_record(record_id)
    return RecordResponse.model_validate(record)


# ---------------------------------------------------------------------------
# Records — soft-delete (archive)
# ---------------------------------------------------------------------------
@router.patch(
    "/{record_id}/archive",
    response_model=RecordResponse,
)
async def archive_record(record_id: int, db: DbDep) -> RecordResponse:
    """Soft-delete (archive) a record.

    Logs are automatically tagged with request correlation ID (cid).
    """
    logger.info("record_archive", extra={"id": record_id})
    record = await soft_delete_record(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found or already archived",
        )
    logger.info("record_archived", extra={"id": record_id})
    return RecordResponse.model_validate(record)


# ---------------------------------------------------------------------------
# Records — delete
# ---------------------------------------------------------------------------
@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_record(record_id: int, db: DbDep) -> None:
    """Hard-delete a record.

    Invalidates any cached version.
    Logs are automatically tagged with request correlation ID (cid).
    """
    logger.info("record_delete", extra={"id": record_id})
    record = await delete_record_op(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    # Invalidate cache since record no longer exists
    await cache.invalidate_record(record_id)
    logger.info("record_deleted", extra={"id": record_id})


# ============================================================================
# Auth Examples: v1 Bearer Token + Session-based Auth
# ============================================================================


@router.post("/auth/login", response_model=SessionResponse)
async def login_session(user_id: str) -> SessionResponse:
    """Create a session (learning example for session-based auth).

    In production: verify password hash, check rate limits, use HTTPS only, etc.
    Response includes Set-Cookie header with session_id.
    """
    session_id, cookie_value = create_session(user_id, {"role": "default"})
    logger.info("login_success", extra={"user_id": user_id})

    # Return token explicitly (FastAPI handles Set-Cookie automatically via Response)
    return SessionResponse(session_id=session_id, message="Session created")


@router.get("/{record_id}/secure", response_model=RecordResponse)
async def get_record_secured(
    record_id: int,
    db: DbDep,
    session: SessionDep,
) -> RecordResponse:
    """Get record with session-based auth (learning example).

    Requires valid session cookie. Try:
    1. POST /api/v1/records/auth/login?user_id=testuser
    2. GET /api/v1/records/1/secure (with cookie from step 1)

    Production: Use JWT or centralized session store (Redis).
    """
    logger.info(
        "get_record_secured",
        extra={"record_id": record_id, "user_id": session.get("user_id")},
    )
    record = await get_record_op(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return RecordResponse.model_validate(record)


@router.post(
    "/batch/protected",
    response_model=BatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_records_batch_protected(
    body: BatchRecordsRequest,
    db: DbDep,
    token: BearerTokenDep,
) -> BatchCreateResponse:
    """Batch create with bearer token auth (learning example).

    Requires: Authorization: Bearer <token>
    Set API_V1_BEARER_TOKEN in .env, then:

    curl -X POST http://localhost:8000/api/v1/records/batch/protected \\
      -H "Authorization: Bearer dev-secret-bearer-token" \\
      -H "Content-Type: application/json" \\
      -d '{"records": [...]}'

    Production: Use API key rotation, rate limiting per key, audit logs.
    """
    logger.info(
        "batch_protected_create",
        extra={"count": len(body.records), "token_prefix": token[:10]},
    )
    records = await create_records_batch_op(db, body.records)
    logger.info("batch_protected_created", extra={"count": len(records)})
    return BatchCreateResponse(created=len(records), impl="optimized")
