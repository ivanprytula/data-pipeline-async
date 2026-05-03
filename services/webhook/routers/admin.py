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
