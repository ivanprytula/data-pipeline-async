"""Pydantic v2 schemas for the webhook service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WebhookEventPayloadRequest(BaseModel):
    """Inbound webhook payload from an external source (Stripe, Segment, etc.)."""

    data: dict[str, Any] = Field(..., description="Webhook event payload")


class WebhookSourceResponse(BaseModel):
    """Webhook source configuration response."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    description: str | None
    signing_algorithm: str
    rate_limit_per_minute: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WebhookEventResponse(BaseModel):
    """Webhook event audit log entry response."""

    model_config = {"from_attributes": True}

    id: int
    source: str
    delivery_id: str
    idempotency_key: str | None
    signature_valid: bool
    status: str
    processing_attempts: int
    last_error: str | None
    published_to_kafka: bool
    kafka_offset: int | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WebhookSourceCreateRequest(BaseModel):
    """Request body for registering a new webhook source."""

    name: str = Field(..., description="Unique source name (e.g., 'stripe')")
    description: str | None = Field(None, description="Human-readable description")
    signing_key_secret_name: str | None = Field(
        None,
        description="Secrets Manager key name for HMAC signing key",
    )
    signing_algorithm: str = Field(
        "hmac-sha256",
        description="Signature algorithm (default: hmac-sha256)",
    )
    rate_limit_per_minute: int = Field(
        100,
        ge=1,
        le=10_000,
        description="Max inbound requests per minute from this source",
    )


class WebhookSourceUpdateRequest(BaseModel):
    """Request body for updating an existing webhook source (PATCH)."""

    description: str | None = None
    signing_key_secret_name: str | None = None
    signing_algorithm: str | None = None
    rate_limit_per_minute: int | None = Field(None, ge=1, le=10_000)
    is_active: bool | None = None


class WebhookReplayRequest(BaseModel):
    """Request body for bulk-queuing failed webhook events for replay."""

    source: str = Field(..., description="Source to replay events from")
    date_from: datetime | None = Field(
        None, description="Start of date range (inclusive)"
    )
    date_to: datetime | None = Field(None, description="End of date range (inclusive)")
    status_filter: str = Field(
        "failed",
        description="Only replay events with this status",
    )
    limit: int = Field(
        500,
        ge=1,
        le=5_000,
        description="Maximum events to enqueue in one request",
    )


class WebhookReplayResponse(BaseModel):
    """Response for bulk-replay enqueue operation."""

    source: str
    enqueued_count: int
    status_filter: str
    message: str
