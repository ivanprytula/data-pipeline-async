"""Webhook service constants — single source of truth for webhook-specific values."""

# ---------------------------------------------------------------------------
# Payload limits
# ---------------------------------------------------------------------------
WEBHOOK_EVENTS_MAX_PAYLOAD_SIZE: int = 10_000_000  # 10 MB max payload

# ---------------------------------------------------------------------------
# HTTP header names
# ---------------------------------------------------------------------------
WEBHOOK_SIGNATURE_HEADER_NAME: str = "X-Webhook-Signature"
WEBHOOK_DELIVERY_ID_HEADER_NAME: str = "X-Delivery-ID"
WEBHOOK_TIMESTAMP_HEADER_NAME: str = "X-Timestamp"

# ---------------------------------------------------------------------------
# Signing algorithms
# ---------------------------------------------------------------------------
WEBHOOK_SIGNATURE_ALGORITHM_HMAC_SHA256: str = "HMAC-SHA256"

# ---------------------------------------------------------------------------
# Event status values
# ---------------------------------------------------------------------------
WEBHOOK_EVENT_STATUS_PENDING: str = "pending"
WEBHOOK_EVENT_STATUS_PROCESSING: str = "processing"
WEBHOOK_EVENT_STATUS_PUBLISHED: str = "published"
WEBHOOK_EVENT_STATUS_FAILED: str = "failed"
WEBHOOK_EVENT_STATUS_REPLAY_QUEUED: str = "replay_queued"

# ---------------------------------------------------------------------------
# Replay / retry settings
# ---------------------------------------------------------------------------
WEBHOOK_REPLAY_MAX_ATTEMPTS: int = 5
WEBHOOK_REPLAY_BACKOFF_BASE_SECONDS: float = 2.0  # exponential backoff multiplier

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
WEBHOOK_DEFAULT_RATE_LIMIT_PER_MINUTE: int = 60
