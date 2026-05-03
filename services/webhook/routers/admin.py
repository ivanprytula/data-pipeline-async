"""Admin API routes for webhook source management and event inspection.

All admin endpoints require a valid Bearer token (configured via the
``ADMIN_TOKEN`` environment variable). This is a simple shared-secret
approach suitable for internal tooling; replace with proper OAuth/RBAC
for multi-tenant production use.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from services.webhook.core.database import get_db
from services.webhook.crud import (
    bulk_mark_events_for_replay,
    create_webhook_source,
    get_webhook_events,
    list_webhook_sources,
    update_webhook_source,
)
from services.webhook.schemas import (
    WebhookEventResponse,
    WebhookReplayRequest,
    WebhookReplayResponse,
    WebhookSourceCreateRequest,
    WebhookSourceResponse,
    WebhookSourceUpdateRequest,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_bearer_scheme = HTTPBearer(auto_error=True)

type DbDep = Annotated[AsyncSession, Depends(get_db)]


def _verify_admin_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> str:
    """Validate the Bearer token in the Authorization header.

    Args:
        credentials: Parsed HTTP Bearer credentials.

    Returns:
        The token string if valid.

    Raises:
        HTTPException: 401 if token is missing or invalid.
    """
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin auth is not configured (ADMIN_TOKEN not set)",
        )
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


type AdminDep = Annotated[str, Depends(_verify_admin_token)]


@router.get("/sources", response_model=list[WebhookSourceResponse])
async def list_sources(
    _token: AdminDep,
    db: DbDep,
) -> list[WebhookSourceResponse]:
    """List all registered webhook sources.

    Args:
        _token: Validated admin Bearer token.
        db: Async database session.

    Returns:
        List of webhook source configurations.
    """
    sources = await list_webhook_sources(db)
    return [WebhookSourceResponse.model_validate(s) for s in sources]


@router.post(
    "/sources",
    response_model=WebhookSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_source(
    request: WebhookSourceCreateRequest,
    _token: AdminDep,
    db: DbDep,
) -> WebhookSourceResponse:
    """Register a new webhook source.

    Args:
        request: Source configuration.
        _token: Validated admin Bearer token.
        db: Async database session.

    Returns:
        Created webhook source.

    Raises:
        409: A source with this name already exists.
    """
    from sqlalchemy.exc import IntegrityError

    try:
        source = await create_webhook_source(
            session=db,
            name=request.name,
            description=request.description,
            signing_key_secret_name=request.signing_key_secret_name,
            signing_algorithm=request.signing_algorithm,
            rate_limit_per_minute=request.rate_limit_per_minute,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Webhook source '{request.name}' already exists",
        ) from exc

    logger.info("webhook_source_created", extra={"source": source.name})
    return WebhookSourceResponse.model_validate(source)


@router.patch("/sources/{name}", response_model=WebhookSourceResponse)
async def patch_source(
    name: str,
    request: WebhookSourceUpdateRequest,
    _token: AdminDep,
    db: DbDep,
) -> WebhookSourceResponse:
    """Update an existing webhook source (e.g., pause/resume).

    Args:
        name: Source name to update.
        request: Fields to update (all optional).
        _token: Validated admin Bearer token.
        db: Async database session.

    Returns:
        Updated webhook source.

    Raises:
        404: Source not found.
    """
    updates: dict[str, Any] = {
        k: v for k, v in request.model_dump().items() if v is not None
    }
    source = await update_webhook_source(session=db, name=name, **updates)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook source '{name}' not found",
        )

    logger.info(
        "webhook_source_updated", extra={"source": name, "updates": list(updates)}
    )
    return WebhookSourceResponse.model_validate(source)


@router.get("/webhooks/events", response_model=list[WebhookEventResponse])
async def list_webhook_events(
    _token: AdminDep,
    db: DbDep,
    source: str | None = Query(None, description="Filter by source name"),
    event_status: str | None = Query(
        None, alias="status", description="Filter by status"
    ),
    limit: int = Query(100, ge=1, le=1_000, description="Max results to return"),
) -> list[WebhookEventResponse]:
    """Inspect webhook event history with optional filters.

    Args:
        _token: Validated admin Bearer token.
        db: Async database session.
        source: Filter by source name.
        event_status: Filter by event status.
        limit: Max events to return.

    Returns:
        List of webhook events ordered by creation time descending.
    """
    events = await get_webhook_events(
        session=db,
        source=source,
        event_status=event_status,
        limit=limit,
    )
    return [WebhookEventResponse.model_validate(e) for e in events]


@router.post("/webhooks/replay", response_model=WebhookReplayResponse)
async def replay_webhook_events(
    request: WebhookReplayRequest,
    _token: AdminDep,
    db: DbDep,
) -> WebhookReplayResponse:
    """Bulk-enqueue failed webhook events for replay.

    Marks matching events as ``replay_queued`` so the replay daemon
    will re-publish them to Kafka on its next cycle.

    Args:
        request: Replay filter parameters.
        _token: Validated admin Bearer token.
        db: Async database session.

    Returns:
        Count of events enqueued.
    """
    count = await bulk_mark_events_for_replay(
        session=db,
        source=request.source,
        date_from=request.date_from,
        date_to=request.date_to,
        status_filter=request.status_filter,
        limit=request.limit,
    )
    logger.info(
        "webhook_replay_enqueued",
        extra={"source": request.source, "count": count},
    )
    return WebhookReplayResponse(
        source=request.source,
        enqueued_count=count,
        status_filter=request.status_filter,
        message=f"Enqueued {count} event(s) for replay",
    )


# ── Phase 13.3: API Key Lifecycle Endpoints ───────────────────────────────────


@router.post(
    "/sources/{source_id}/api-keys",
    status_code=status.HTTP_201_CREATED,
)
async def create_source_api_key(
    source_id: int,
    _token: AdminDep,
    db: DbDep,
    label: str | None = Query(None, description="Optional label for this key"),
) -> dict[str, Any]:
    """Generate a new API key for a webhook source.

    The plaintext key is returned ONCE. Store it securely — it cannot be
    retrieved again (only its Argon2id hash is stored, OWASP A02).

    Args:
        source_id: ID of the webhook source.
        _token: Validated admin Bearer token.
        db: Async database session.
        label: Optional human-readable label.

    Returns:
        JSON with key_id, api_key (plaintext, shown once), key_prefix, created_at.

    Raises:
        404: Source not found.
    """
    from sqlalchemy import select as sa_select

    from services.webhook.models import WebhookSource
    from services.webhook.services.api_keys import create_api_key

    result = await db.execute(
        sa_select(WebhookSource).where(WebhookSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook source with id={source_id} not found",
        )

    api_key, plaintext = await create_api_key(db=db, source_id=source_id, label=label)
    logger.info(
        "admin_api_key_created",
        extra={"source_id": source_id, "key_id": api_key.id},
    )
    return {
        "key_id": api_key.id,
        "api_key": plaintext,
        "key_prefix": api_key.key_prefix,
        "label": api_key.label,
        "created_at": api_key.created_at.isoformat(),
    }


@router.delete(
    "/sources/{source_id}/api-keys/{key_id}",
    status_code=status.HTTP_200_OK,
)
async def revoke_source_api_key(
    source_id: int,
    key_id: int,
    _token: AdminDep,
    db: DbDep,
) -> dict[str, Any]:
    """Revoke an API key for a webhook source.

    Args:
        source_id: ID of the webhook source.
        key_id: ID of the API key to revoke.
        _token: Validated admin Bearer token.
        db: Async database session.

    Returns:
        Confirmation with key_id and revoked_at.

    Raises:
        404: Key not found or already revoked.
    """
    from services.webhook.services.api_keys import revoke_api_key

    api_key = await revoke_api_key(db=db, source_id=source_id, key_id=key_id)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active API key {key_id} for source {source_id} not found",
        )
    logger.info(
        "admin_api_key_revoked",
        extra={"source_id": source_id, "key_id": key_id},
    )
    return {
        "key_id": api_key.id,
        "revoked_at": api_key.revoked_at.isoformat() if api_key.revoked_at else None,
        "message": "API key revoked successfully",
    }


@router.post(
    "/sources/{source_id}/rotate-key",
    status_code=status.HTTP_200_OK,
)
async def rotate_signing_key(
    source_id: int,
    _token: AdminDep,
    db: DbDep,
) -> dict[str, Any]:
    """Rotate the HMAC signing key for a webhook source.

    Increments signing_key_version and marks the previous version as deprecated
    with a 7-day grace period. During the grace period, events signed with either
    the new or deprecated key are accepted.

    The new signing key must be provisioned in Secrets Manager under
    ``data-zoo/webhook/<source>/v<new_version>/signing-key`` BEFORE calling
    this endpoint.

    Args:
        source_id: ID of the webhook source.
        _token: Validated admin Bearer token.
        db: Async database session.

    Returns:
        New key version and deprecation info.

    Raises:
        404: Source not found.
    """
    from sqlalchemy import select as sa_select

    from services.webhook.models import WebhookSource

    result = await db.execute(
        sa_select(WebhookSource).where(WebhookSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook source with id={source_id} not found",
        )

    from datetime import UTC, datetime

    old_version = source.signing_key_version
    new_version = old_version + 1

    source.deprecated_key_version = old_version
    source.key_deprecated_at = datetime.now(UTC).replace(tzinfo=None)
    source.signing_key_version = new_version

    await db.commit()
    await db.refresh(source)

    logger.info(
        "webhook_signing_key_rotated",
        extra={
            "source_id": source_id,
            "source_name": source.name,
            "old_version": old_version,
            "new_version": new_version,
        },
    )
    return {
        "source_id": source_id,
        "source_name": source.name,
        "new_version": new_version,
        "deprecated_version": old_version,
        "deprecated_at": source.key_deprecated_at.isoformat(),
        "grace_period_days": 7,
        "message": (
            f"Key rotated to v{new_version}. "
            f"v{old_version} accepted for 7 days during transition."
        ),
    }
