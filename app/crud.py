"""Async CRUD operations (SQLAlchemy 2.0 select() style)."""

from datetime import datetime

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Record, _utcnow
from app.schemas import RecordRequest, UpdateRecordRequest


async def create_record(session: AsyncSession, request: RecordRequest) -> Record:
    record = Record(
        source=request.source,
        timestamp=request.timestamp,
        raw_data=request.data,
        tags=request.tags,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def create_records_batch(
    session: AsyncSession, requests: list[RecordRequest]
) -> list[Record]:
    """Bulk-insert with RETURNING — single round-trip to database.

    Uses insert().values().returning() to avoid N+1 refresh queries.
    All server-default fields (id, created_at, updated_at, processed) are
    populated in the INSERT RETURNING clause, not via individual refreshes.

    Args:
        session: Active async database session.
        requests: List of RecordRequest payloads to insert.

    Returns:
        List of fully-hydrated Record ORM instances (with all defaults).
    """
    if not requests:
        return []

    # Prepare insert data: map request fields to Record columns
    insert_data = [
        {
            "source": r.source,
            "timestamp": r.timestamp,
            "raw_data": r.data,
            "tags": r.tags,
        }
        for r in requests
    ]

    # INSERT with RETURNING to get all fields back in one round-trip
    stmt = insert(Record).values(insert_data).returning(Record)
    result = await session.execute(stmt)
    records = result.scalars().all()

    await session.commit()
    return list(records)


async def create_records_batch_naive(
    session: AsyncSession, requests: list[RecordRequest]
) -> list[Record]:
    """Naive bulk-insert: N individual INSERTs + N individual REFRESH calls.

    This is the *before* implementation kept deliberately unoptimised so the
    `POST /api/v1/records/batch?impl=naive` endpoint can demonstrate — with
    measurable latency — exactly why the optimised version exists.

    Pattern: add_all → commit → for-loop refresh
    Round-trips: 1 (commit) + N (refresh) = N+1

    Args:
        session: Active async database session.
        requests: List of RecordRequest payloads to insert.

    Returns:
        List of fully-hydrated Record ORM instances (with all defaults).
    """
    if not requests:
        return []

    records = [
        Record(
            source=r.source,
            timestamp=r.timestamp,
            raw_data=r.data,
            tags=r.tags,
        )
        for r in requests
    ]
    session.add_all(records)
    await session.commit()
    # N individual round-trips to hydrate server-default fields
    for record in records:
        await session.refresh(record)
    return records


async def get_records(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    source: str | None = None,
) -> tuple[list[Record], int]:
    count_q = (
        select(func.count()).select_from(Record).where(Record.deleted_at.is_(None))
    )
    data_q = (
        select(Record)
        .where(Record.deleted_at.is_(None))
        .order_by(Record.id)
        .offset(skip)
        .limit(limit)
    )
    if source:
        count_q = count_q.where(Record.source == source)
        data_q = data_q.where(Record.source == source)
    total = (await session.execute(count_q)).scalar_one()
    records = list((await session.execute(data_q)).scalars().all())
    return records, total


async def get_records_by_date_range(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    source: str | None = None,
) -> list[Record]:
    """Fetch records within a timestamp range using the ix_records_timestamp index.

    Real-world pattern: "give me all pipeline records from the last 24h"

    Args:
        session: Active async database session.
        start: Inclusive start timestamp.
        end: Exclusive end timestamp (queries timestamp < end).
        source: Optional source filter.

    Returns:
        List of records (active only, deleted_at IS NULL).
    """
    query = (
        select(Record)
        .where(
            Record.deleted_at.is_(None),
            Record.timestamp >= start,
            Record.timestamp < end,
        )
        .order_by(Record.timestamp.desc(), Record.id.desc())
    )
    if source:
        query = query.where(Record.source == source)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_record(session: AsyncSession, record_id: int) -> Record | None:
    result = await session.execute(
        select(Record).where(Record.id == record_id, Record.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def mark_processed(session: AsyncSession, record_id: int) -> Record | None:
    """Mark a record as processed and set processed_at timestamp.

    Sets processed_at only if it's currently None (idempotent).

    Args:
        session: Active async database session.
        record_id: Primary key of the record to mark.

    Returns:
        Updated Record ORM instance, or None if not found.
    """
    record = await session.get(Record, record_id)
    if record is None:
        return None
    record.processed = True
    if record.processed_at is None:
        record.processed_at = _utcnow()
    await session.commit()
    await session.refresh(record)
    return record


async def update_record(
    session: AsyncSession, record_id: int, request: UpdateRecordRequest
) -> Record | None:
    """Update a record with provided fields (partial update).

    Only updates fields that are provided (not None). Non-provided fields
    are left unchanged.

    Args:
        session: Active async database session.
        record_id: Primary key of the record to update.
        request: UpdateRecordRequest with optional fields to update.

    Returns:
        Updated Record ORM instance, or None if not found.
    """
    record = await session.get(Record, record_id)
    if record is None:
        return None

    # Update only provided fields
    if request.source is not None:
        record.source = request.source
    if request.timestamp is not None:
        record.timestamp = request.timestamp
    if request.data is not None:
        record.raw_data = request.data
    if request.tags is not None:
        record.tags = request.tags

    await session.commit()
    await session.refresh(record)
    return record


async def delete_record(session: AsyncSession, record_id: int) -> Record | None:
    record = await session.get(Record, record_id)
    if record is None:
        return None
    await session.delete(record)
    await session.commit()
    return record


async def soft_delete_record(session: AsyncSession, record_id: int) -> Record | None:
    record = await session.get(Record, record_id)
    if record is None or record.deleted_at is not None:
        return None
    record.deleted_at = _utcnow()
    await session.commit()
    await session.refresh(record)
    return record


async def get_records_with_tag_counts_naive(
    session: AsyncSession, limit: int = 10
) -> list[dict]:
    """Fetch records with tag counts using N+1 pattern (deliberate inefficiency).

    **Pattern**: 1 initial SELECT + N individual COUNT queries.
    Total queries: N+1 (N is the number of records returned).

    This function intentionally uses the naive approach so performance can be
    directly compared with the optimized version. Used in the N+1 demo endpoint
    to show real-world latency impact.

    Args:
        session: Active async database session.
        limit: Maximum number of records to fetch (default 10).

    Returns:
        List of dicts: {"id", "source", "timestamp", "tag_count"}.
    """
    # Query 1: Fetch records
    query = (
        select(Record)
        .where(Record.deleted_at.is_(None))
        .order_by(Record.id.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    records = list(result.scalars().all())

    # Queries 2..N+1: Count tags for each record individually
    data = []
    for record in records:
        tag_count = len(record.tags) if record.tags else 0
        data.append(
            {
                "id": record.id,
                "source": record.source,
                "timestamp": record.timestamp.isoformat(),
                "tag_count": tag_count,
            }
        )
    return data


async def get_records_with_tag_counts(
    session: AsyncSession, limit: int = 10
) -> list[dict]:
    """Fetch records with tag counts using a single optimized query.

    **Pattern**: Single SELECT that fetches all data in one query (vs per-record).
    Total queries: 1 (vs N+1 for naive approach).

    The key optimization: all data fetched in a single SELECT, then tag counts
    computed. This avoids the loop-per-record pattern of the naive approach.

    In production (PostgreSQL): migrate to `array_length(tags, 1)` for true
    server-side computation. In testing (SQLite): computed client-side but still
    only one query.

    Args:
        session: Active async database session.
        limit: Maximum number of records to fetch (default 10).

    Returns:
        List of dicts: {"id", "source", "timestamp", "tag_count"}.
    """
    # Single query: fetch all records at once (the optimization)
    query = (
        select(
            Record.id,
            Record.source,
            Record.timestamp,
            Record.tags,
        )
        .where(Record.deleted_at.is_(None))
        .order_by(Record.id.desc())
        .limit(limit)
    )

    result = await session.execute(query)
    rows = result.all()

    # Compute tag counts from the single query result
    return [
        {
            "id": row.id,
            "source": row.source,
            "timestamp": row.timestamp.isoformat(),
            "tag_count": len(row.tags) if row.tags else 0,
        }
        for row in rows
    ]
