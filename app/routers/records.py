"""Records resource — all CRUD routes."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import (
    create_record as create_record_op,
)
from app.crud import (
    create_records_batch as create_records_batch_op,
)
from app.crud import (
    delete_record as delete_record_op,
)
from app.crud import (
    get_record as get_record_op,
)
from app.crud import (
    get_records,
    mark_processed,
    soft_delete_record,
)
from app.database import get_db
from app.schemas import (
    BatchRecordsRequest,
    PaginationMeta,
    RecordListResponse,
    RecordRequest,
    RecordResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/records", tags=["records"])

type DbDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Records — single create
# ---------------------------------------------------------------------------
@router.post(
    "",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_record(request: RecordRequest, db: DbDep) -> RecordResponse:
    """Create a single record.

    Logs are automatically tagged with request correlation ID (cid).
    """
    logger.info("record_create", extra={"source": request.source})
    record = await create_record_op(db, request)
    logger.info("record_created", extra={"id": record.id})
    return record  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Records — batch create
# ---------------------------------------------------------------------------
@router.post(
    "/batch",
    status_code=status.HTTP_201_CREATED,
)
async def create_records_batch(request: BatchRecordsRequest, db: DbDep) -> dict:
    """Create multiple records in batch.

    Logs are automatically tagged with request correlation ID (cid).
    """
    logger.info("batch_create", extra={"count": len(request.records)})
    records = await create_records_batch_op(db, request.records)
    logger.info("batch_created", extra={"count": len(records)})
    return {"created": len(records)}


# ---------------------------------------------------------------------------
# Records — list with pagination
# ---------------------------------------------------------------------------
@router.get("", response_model=RecordListResponse)
async def list_records(
    db: DbDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    source: str | None = None,
) -> RecordListResponse:
    """List records with pagination and optional filtering by source."""
    records, total = await get_records(db, skip, limit, source)
    return RecordListResponse(
        records=records,  # type: ignore[arg-type]
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
    """Retrieve a single record by ID."""
    record = await get_record_op(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return record  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Records — mark as processed
# ---------------------------------------------------------------------------
@router.patch(
    "/{record_id}/process",
    response_model=RecordResponse,
)
async def process_record(record_id: int, db: DbDep) -> RecordResponse:
    """Mark a record as processed."""
    record = await mark_processed(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return record  # type: ignore[return-value]


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
    return record  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Records — delete
# ---------------------------------------------------------------------------
@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_record(record_id: int, db: DbDep) -> None:
    """Hard-delete a record.

    Logs are automatically tagged with request correlation ID (cid).
    """
    logger.info("record_delete", extra={"id": record_id})
    record = await delete_record_op(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    logger.info("record_deleted", extra={"id": record_id})
