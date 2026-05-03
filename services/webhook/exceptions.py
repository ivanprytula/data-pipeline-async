"""Webhook service exception hierarchy — import these in routers and services."""

from __future__ import annotations


class WebhookError(Exception):
    """Base class for all webhook service errors."""


class WebhookSourceNotFoundError(WebhookError):
    """Raised when webhook source is not configured or is inactive."""


class WebhookSignatureInvalidError(WebhookError):
    """Raised when HMAC signature validation fails."""


class WebhookEventAlreadyProcessedError(WebhookError):
    """Raised when a webhook delivery_id already exists (exact duplicate)."""


class WebhookPayloadTooLargeError(WebhookError):
    """Raised when webhook payload exceeds the configured size limit."""


class WebhookRateLimitExceededError(WebhookError):
    """Raised when per-source rate limit is exceeded."""
