"""Async CRUD operations (SQLAlchemy 2.0 select() style)."""

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Record, _utcnow
from app.schemas import RecordRequest


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


async def get_record(session: AsyncSession, record_id: int) -> Record | None:
    result = await session.execute(
        select(Record).where(Record.id == record_id, Record.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def mark_processed(session: AsyncSession, record_id: int) -> Record | None:
    record = await session.get(Record, record_id)
    if record is None:
        return None
    record.processed = True
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
