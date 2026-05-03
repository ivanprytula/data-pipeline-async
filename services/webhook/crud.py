"""Webhook CRUD operations — webhook_sources and webhook_events tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.webhook.models import WebhookEvent, WebhookSource


async def get_webhook_source_by_name(
    session: AsyncSession, name: str
) -> WebhookSource | None:
    """Fetch an active webhook source by name.

    Args:
        session: Active async database session.
        name: Webhook source name (e.g., 'stripe', 'segment').

    Returns:
        WebhookSource ORM instance, or None if not found or inactive.
    """
    result = await session.execute(
        select(WebhookSource).where(
            and_(WebhookSource.name == name, WebhookSource.is_active.is_(True))
        )
    )
    return result.scalar_one_or_none()


async def list_webhook_sources(session: AsyncSession) -> list[WebhookSource]:
    """List all webhook sources.

    Args:
        session: Active async database session.

    Returns:
        List of WebhookSource ORM instances.
    """
    result = await session.execute(select(WebhookSource))
    return list(result.scalars().all())


async def create_webhook_event(
    session: AsyncSession,
    source: str,
    delivery_id: str,
    raw_payload: dict,
    headers: dict,
    signature_valid: bool,
    idempotency_key: str | None = None,
) -> WebhookEvent:
    """Create a new webhook event audit log entry.

    Args:
        session: Active async database session.
        source: Webhook source name (e.g., 'stripe').
        delivery_id: Unique delivery ID (UUID) from webhook source.
        raw_payload: Raw webhook payload (JSON).
        headers: HTTP headers from webhook delivery.
        signature_valid: Whether signature validation passed.
        idempotency_key: Optional idempotency key for deduplication.

    Returns:
        Newly created WebhookEvent ORM instance.
    """
    event = WebhookEvent(
        source=source,
        delivery_id=delivery_id,
        raw_payload=raw_payload,
        headers=headers,
        signature_valid=signature_valid,
        idempotency_key=idempotency_key,
        status="pending",
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def get_webhook_event_by_delivery_id(
    session: AsyncSession, delivery_id: str
) -> WebhookEvent | None:
    """Fetch a webhook event by delivery ID.

    Args:
        session: Active async database session.
        delivery_id: Unique delivery ID from webhook source.

    Returns:
        WebhookEvent ORM instance or None.
    """
    result = await session.execute(
        select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id)
    )
    return result.scalar_one_or_none()


async def get_webhook_event_by_idempotency_key(
    session: AsyncSession, idempotency_key: str
) -> WebhookEvent | None:
    """Fetch a webhook event by idempotency key.

    Args:
        session: Active async database session.
        idempotency_key: Idempotency key from webhook payload.

    Returns:
        WebhookEvent ORM instance or None.
    """
    result = await session.execute(
        select(WebhookEvent).where(WebhookEvent.idempotency_key == idempotency_key)
    )
    return result.scalar_one_or_none()


async def update_webhook_event_status(
    session: AsyncSession,
    event_id: int,
    status: str,
    published_to_kafka: bool = False,
    kafka_offset: int | None = None,
    last_error: str | None = None,
    processed_at: datetime | None = None,
) -> WebhookEvent | None:
    """Update webhook event status and processing metadata.

    Args:
        session: Active async database session.
        event_id: Webhook event primary key.
        status: New status value.
        published_to_kafka: Whether the event was successfully published.
        kafka_offset: Kafka message offset, if published.
        last_error: Error description, if failed.
        processed_at: Timestamp of final status change.

    Returns:
        Updated WebhookEvent ORM instance, or None if not found.
    """
    result = await session.execute(
        select(WebhookEvent).where(WebhookEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        return None

    event.status = status
    event.processing_attempts += 1
    if published_to_kafka:
        event.published_to_kafka = True
    if kafka_offset is not None:
        event.kafka_offset = kafka_offset
    if last_error is not None:
        event.last_error = last_error
    if processed_at is not None:
        event.processed_at = processed_at

    await session.commit()
    await session.refresh(event)
    return event


async def get_webhook_events_for_replay(
    session: AsyncSession, limit: int = 100
) -> list[WebhookEvent]:
    """Fetch events queued for replay.

    Args:
        session: Active async database session.
        limit: Maximum number of events to return.

    Returns:
        List of WebhookEvent ORM instances with status 'replay_queued'.
    """
    result = await session.execute(
        select(WebhookEvent).where(WebhookEvent.status == "replay_queued").limit(limit)
    )
    return list(result.scalars().all())


async def create_webhook_source(
    session: AsyncSession,
    name: str,
    description: str | None = None,
    signing_key_secret_name: str | None = None,
    signing_algorithm: str = "hmac-sha256",
    rate_limit_per_minute: int = 100,
) -> WebhookSource:
    """Create a new webhook source configuration.

    Args:
        session: Active async database session.
        name: Unique source name (e.g., 'stripe', 'segment').
        description: Human-readable description.
        signing_key_secret_name: Secrets Manager key name for HMAC signing key.
        signing_algorithm: Algorithm used for signature validation.
        rate_limit_per_minute: Max requests per minute from this source.

    Returns:
        Newly created WebhookSource ORM instance.
    """
    source = WebhookSource(
        name=name,
        description=description,
        signing_key_secret_name=signing_key_secret_name,
        signing_algorithm=signing_algorithm,
        rate_limit_per_minute=rate_limit_per_minute,
        is_active=True,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def update_webhook_source(
    session: AsyncSession,
    name: str,
    **kwargs,
) -> WebhookSource | None:
    """Update an existing webhook source configuration field(s).

    Only the keys present in ``kwargs`` are updated.

    Args:
        session: Active async database session.
        name: Source name to look up.
        **kwargs: Field/value pairs to update (e.g., ``is_active=False``).

    Returns:
        Updated WebhookSource ORM instance, or None if not found.
    """
    result = await session.execute(
        select(WebhookSource).where(WebhookSource.name == name)
    )
    source = result.scalar_one_or_none()
    if not source:
        return None

    allowed_fields = {
        "description",
        "signing_key_secret_name",
        "signing_algorithm",
        "rate_limit_per_minute",
        "is_active",
    }
    for field, value in kwargs.items():
        if field in allowed_fields:
            setattr(source, field, value)

    await session.commit()
    await session.refresh(source)
    return source


async def get_webhook_events(
    session: AsyncSession,
    source: str | None = None,
    event_status: str | None = None,
    limit: int = 100,
) -> list[WebhookEvent]:
    """Fetch webhook events with optional filters.

    Args:
        session: Active async database session.
        source: Filter by source name.
        event_status: Filter by status (e.g., 'failed', 'published').
        limit: Maximum number of events to return.

    Returns:
        List of WebhookEvent ORM instances ordered by creation time descending.
    """
    query = select(WebhookEvent).order_by(WebhookEvent.created_at.desc()).limit(limit)

    conditions = []
    if source is not None:
        conditions.append(WebhookEvent.source == source)
    if event_status is not None:
        conditions.append(WebhookEvent.status == event_status)
    if conditions:
        query = query.where(and_(*conditions))

    result = await session.execute(query)
    return list(result.scalars().all())


async def bulk_mark_events_for_replay(
    session: AsyncSession,
    source: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status_filter: str = "failed",
    limit: int = 500,
) -> int:
    """Mark a batch of events as 'replay_queued' for re-processing.

    Args:
        session: Active async database session.
        source: Source to filter events.
        date_from: Inclusive lower bound on created_at.
        date_to: Inclusive upper bound on created_at.
        status_filter: Only mark events with this current status.
        limit: Maximum events to mark in one call.

    Returns:
        Number of events updated.
    """
    conditions = [
        WebhookEvent.source == source,
        WebhookEvent.status == status_filter,
    ]
    if date_from is not None:
        conditions.append(WebhookEvent.created_at >= date_from)
    if date_to is not None:
        conditions.append(WebhookEvent.created_at <= date_to)

    result = await session.execute(
        select(WebhookEvent).where(and_(*conditions)).limit(limit)
    )
    events = result.scalars().all()
    count = 0
    for event in events:
        event.status = "replay_queued"
        count += 1

    if count:
        await session.commit()

    return count
