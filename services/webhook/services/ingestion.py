"""Webhook ingestion service — business logic for webhook reception pipeline."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.webhook.constants import (
    WEBHOOK_EVENT_STATUS_FAILED,
    WEBHOOK_EVENT_STATUS_PUBLISHED,
    WEBHOOK_EVENTS_MAX_PAYLOAD_SIZE,
)
from services.webhook.crud import (
    create_webhook_event,
    get_webhook_event_by_delivery_id,
    get_webhook_event_by_idempotency_key,
    get_webhook_source_by_name,
    update_webhook_event_status,
)
from services.webhook.exceptions import (
    WebhookEventAlreadyProcessedError,
    WebhookPayloadTooLargeError,
    WebhookSourceNotFoundError,
)


logger = logging.getLogger(__name__)


async def ingest_webhook_event(
    session: AsyncSession,
    source: str,
    delivery_id: str,
    raw_payload: dict,
    headers: dict,
    signature_valid: bool,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Ingest webhook event with deduplication and audit logging.

    Workflow:
    1. Verify webhook source is configured and active
    2. Check payload size (max 10 MB)
    3. Check for duplicate delivery_id (exact duplicate prevention)
    4. Check for duplicate idempotency_key (logical duplicate prevention)
    5. Create audit log entry with 'pending' status
    6. Return webhook event metadata for downstream processing

    Args:
        session: Active async database session.
        source: Webhook source name (e.g., 'stripe', 'segment').
        delivery_id: Unique delivery ID (UUID) from webhook source.
        raw_payload: Raw webhook payload (JSONB).
        headers: HTTP headers from webhook delivery (dict).
        signature_valid: Whether signature validation passed.
        idempotency_key: Optional idempotency key for logical deduplication.

    Returns:
        Dictionary with webhook event metadata:
        - event_id: Database ID
        - delivery_id: Webhook delivery ID
        - status: Current processing status
        - signature_valid: Whether signature was valid
        - is_duplicate: Whether this is a duplicate (idempotency_key match)

    Raises:
        WebhookSourceNotFoundError: If source not configured or inactive.
        WebhookPayloadTooLargeError: If payload exceeds size limit.
        WebhookEventAlreadyProcessedError: If delivery_id already exists.
    """
    # Step 1: Verify webhook source is configured and active
    source_config = await get_webhook_source_by_name(session, source)
    if not source_config:
        logger.warning(
            "webhook_source_not_found",
            extra={"source": source},
        )
        raise WebhookSourceNotFoundError(
            f"Webhook source '{source}' not found or inactive"
        )

    # Step 2: Validate payload size
    payload_bytes = json.dumps(raw_payload).encode("utf-8")
    if len(payload_bytes) > WEBHOOK_EVENTS_MAX_PAYLOAD_SIZE:
        logger.warning(
            "webhook_payload_too_large",
            extra={
                "source": source,
                "delivery_id": delivery_id[:8],
                "size_bytes": len(payload_bytes),
                "limit_bytes": WEBHOOK_EVENTS_MAX_PAYLOAD_SIZE,
            },
        )
        raise WebhookPayloadTooLargeError(
            f"Payload size {len(payload_bytes)} exceeds limit "
            f"({WEBHOOK_EVENTS_MAX_PAYLOAD_SIZE})"
        )

    # Step 3: Check for exact duplicate (delivery_id)
    existing_by_delivery_id = await get_webhook_event_by_delivery_id(
        session, delivery_id
    )
    if existing_by_delivery_id:
        logger.info(
            "webhook_duplicate_delivery_id",
            extra={
                "source": source,
                "delivery_id": delivery_id[:8],
                "existing_event_id": existing_by_delivery_id.id,
            },
        )
        raise WebhookEventAlreadyProcessedError(
            f"Webhook event with delivery_id {delivery_id} already exists"
        )

    # Step 4: Check for logical duplicate (idempotency_key)
    is_duplicate = False
    if idempotency_key:
        existing_by_idempotency = await get_webhook_event_by_idempotency_key(
            session, idempotency_key
        )
        if existing_by_idempotency:
            logger.info(
                "webhook_duplicate_idempotency_key",
                extra={
                    "source": source,
                    "delivery_id": delivery_id[:8],
                    "idempotency_key": idempotency_key[:8],
                    "existing_event_id": existing_by_idempotency.id,
                },
            )
            is_duplicate = True

    # Step 5: Create audit log entry
    event = await create_webhook_event(
        session=session,
        source=source,
        delivery_id=delivery_id,
        raw_payload=raw_payload,
        headers=headers,
        signature_valid=signature_valid,
        idempotency_key=idempotency_key,
    )

    logger.info(
        "webhook_event_ingested",
        extra={
            "source": source,
            "event_id": event.id,
            "delivery_id": delivery_id[:8],
            "signature_valid": signature_valid,
            "is_duplicate": is_duplicate,
        },
    )

    return {
        "event_id": event.id,
        "delivery_id": event.delivery_id,
        "status": event.status,
        "signature_valid": event.signature_valid,
        "is_duplicate": is_duplicate,
    }


async def mark_webhook_event_as_published(
    session: AsyncSession,
    event_id: int,
    kafka_offset: int | None = None,
) -> dict[str, Any]:
    """Mark webhook event as published to Kafka.

    Args:
        session: Active async database session.
        event_id: Webhook event ID.
        kafka_offset: Kafka message offset (optional).

    Returns:
        Dictionary with updated event metadata.
    """
    event = await update_webhook_event_status(
        session=session,
        event_id=event_id,
        status=WEBHOOK_EVENT_STATUS_PUBLISHED,
        published_to_kafka=True,
        kafka_offset=kafka_offset,
        processed_at=datetime.now(UTC).replace(tzinfo=None),
    )

    if not event:
        logger.error(
            "webhook_event_not_found",
            extra={"event_id": event_id},
        )
        raise ValueError(f"Webhook event {event_id} not found")

    logger.info(
        "webhook_event_published",
        extra={
            "event_id": event_id,
            "kafka_offset": kafka_offset,
        },
    )

    return {
        "event_id": event.id,
        "status": event.status,
        "published_to_kafka": event.published_to_kafka,
        "kafka_offset": event.kafka_offset,
    }


async def mark_webhook_event_as_failed(
    session: AsyncSession,
    event_id: int,
    error_message: str,
) -> dict[str, Any]:
    """Mark webhook event as failed.

    Args:
        session: Active async database session.
        event_id: Webhook event ID.
        error_message: Error description.

    Returns:
        Dictionary with updated event metadata.
    """
    event = await update_webhook_event_status(
        session=session,
        event_id=event_id,
        status=WEBHOOK_EVENT_STATUS_FAILED,
        last_error=error_message,
        processed_at=datetime.now(UTC).replace(tzinfo=None),
    )

    if not event:
        logger.error(
            "webhook_event_not_found",
            extra={"event_id": event_id},
        )
        raise ValueError(f"Webhook event {event_id} not found")

    logger.warning(
        "webhook_event_failed",
        extra={
            "event_id": event_id,
            "error": error_message,
            "attempts": event.processing_attempts,
        },
    )

    return {
        "event_id": event.id,
        "status": event.status,
        "last_error": event.last_error,
        "processing_attempts": event.processing_attempts,
    }
