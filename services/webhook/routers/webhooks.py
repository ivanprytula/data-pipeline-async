"""Webhook routes — event ingestion endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.webhook.core.database import get_db
from services.webhook.crud import (
    get_webhook_event_by_delivery_id,
    update_webhook_event_status,
)
from services.webhook.exceptions import (
    WebhookEventAlreadyProcessedError,
    WebhookPayloadTooLargeError,
    WebhookSourceNotFoundError,
)
from services.webhook.schemas import WebhookEventResponse
from services.webhook.services.ingestion import ingest_webhook_event
from services.webhook.services.kafka_publisher import publish_webhook_event
from services.webhook.services.signature import validate_signature


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

type DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/{source}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(
    source: str,
    raw_request: Request,
    db: DbDep,
    x_delivery_id: str | None = Header(None),
    x_webhook_signature: str | None = Header(None),
    x_timestamp: str | None = Header(None),
) -> dict[str, Any]:
    """Receive a webhook event from an external source.

    Validates HMAC-SHA256 signature, deduplicates, writes an audit log entry,
    and asynchronously publishes to Kafka. Returns 202 Accepted immediately.

    Args:
        source: Webhook source name (e.g., 'stripe', 'segment', 'zapier').
        raw_request: Raw FastAPI request (used to read body bytes for HMAC).
        db: Async database session.
        x_delivery_id: Unique delivery ID from webhook source (UUID).
        x_webhook_signature: HMAC-SHA256 signature for payload validation.
        x_timestamp: Webhook timestamp header.

    Returns:
        202 Accepted with delivery_id, event_id, and status.

    Raises:
        401: Signature header present but invalid.
        409: Duplicate delivery_id (already processed).
        413: Payload exceeds 10 MB limit.
        503: Webhook source not configured or inactive.
    """
    # Read raw body bytes BEFORE JSON parsing (HMAC validates raw bytes)
    body_bytes = await raw_request.body()

    # Parse JSON payload from raw bytes
    try:
        raw_payload: dict[str, Any] = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    delivery_id = x_delivery_id or str(uuid4())
    idempotency_key = raw_payload.get("idempotency_key") if raw_payload else None

    # Validate HMAC signature — reject if header present but invalid
    if x_webhook_signature is not None:
        sig_valid = await validate_signature(
            body=body_bytes,
            header_signature=x_webhook_signature,
            source=source,
        )
        if not sig_valid:
            logger.warning(
                "webhook_signature_rejected",
                extra={"source": source, "delivery_id": delivery_id[:8]},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
        signature_valid = True
    else:
        signature_valid = False  # unsigned — stored in audit log but allowed

    logger.info(
        "webhook_received",
        extra={
            "source": source,
            "delivery_id": delivery_id[:8],
            "signature_valid": signature_valid,
            "has_timestamp": x_timestamp is not None,
        },
    )

    try:
        result = await ingest_webhook_event(
            session=db,
            source=source,
            delivery_id=delivery_id,
            raw_payload=raw_payload,
            headers={
                "x_delivery_id": x_delivery_id or "not-provided",
                "x_webhook_signature": x_webhook_signature or "not-provided",
                "x_timestamp": x_timestamp or "not-provided",
            },
            signature_valid=signature_valid,
            idempotency_key=idempotency_key,
        )
    except WebhookSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Webhook source '{source}' is not configured or inactive",
        ) from exc
    except WebhookEventAlreadyProcessedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Webhook event already processed (duplicate delivery_id)",
        ) from exc
    except WebhookPayloadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload exceeds size limit (10 MB)",
        ) from exc
    except Exception as exc:
        logger.error(
            "webhook_ingestion_error",
            extra={"source": source, "delivery_id": delivery_id[:8], "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        ) from exc

    event_id: int = result["event_id"]

    # Fire-and-forget Kafka publish (errors logged, do not affect HTTP response)
    asyncio.ensure_future(
        _publish_and_update(
            db_session_factory=db.get_bind(),  # pass engine for new session
            event_id=event_id,
            source=source,
            delivery_id=delivery_id,
            payload=raw_payload,
        )
    )

    return {
        "status": "accepted",
        "event_id": event_id,
        "delivery_id": result["delivery_id"],
        "is_duplicate": result["is_duplicate"],
        "message": (
            "Webhook received and queued for processing"
            if not result["is_duplicate"]
            else "Webhook duplicate detected (idempotency_key match, accepted)"
        ),
    }


async def _publish_and_update(
    db_session_factory: Any,
    event_id: int,
    source: str,
    delivery_id: str,
    payload: dict[str, Any],
) -> None:
    """Publish webhook event to Kafka and update audit log status.

    Runs as a fire-and-forget coroutine. Uses a new database session so it
    does not share state with the request's session (which may already be
    closed by the time this runs).

    Args:
        db_session_factory: SQLAlchemy engine for creating a new session.
        event_id: Database ID of the webhook_events row.
        source: Webhook source name.
        delivery_id: Webhook delivery ID.
        payload: Raw payload dict.
    """
    from services.webhook.core.database import AsyncSessionLocal

    offset = await publish_webhook_event(
        source=source,
        event_id=event_id,
        delivery_id=delivery_id,
        payload=payload,
    )

    async with AsyncSessionLocal() as session:
        if offset is not None:
            from datetime import UTC, datetime

            await update_webhook_event_status(
                session=session,
                event_id=event_id,
                status="published",
                published_to_kafka=True,
                kafka_offset=offset,
                processed_at=datetime.now(UTC).replace(tzinfo=None),
            )
        else:
            await update_webhook_event_status(
                session=session,
                event_id=event_id,
                status="failed",
                last_error="Kafka publish failed",
            )


@router.get("/{source}/{delivery_id}", response_model=WebhookEventResponse)
async def get_webhook_event(
    source: str,
    delivery_id: str,
    db: DbDep,
) -> WebhookEventResponse:
    """Get webhook event audit record by delivery ID.

    Args:
        source: Webhook source name (used to scope the lookup).
        delivery_id: Unique delivery ID from webhook source.
        db: Async database session.

    Returns:
        WebhookEventResponse with full audit record.

    Raises:
        404: Webhook event not found.
    """
    event = await get_webhook_event_by_delivery_id(db, delivery_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook event with delivery_id '{delivery_id}' not found",
        )

    if event.source != source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook event '{delivery_id}' not found for source '{source}'",
        )

    return WebhookEventResponse.model_validate(event)
