"""Structured JSON logging setup — runs once at app startup."""

import logging
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from app.config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Context variable for request correlation ID (cid)
# ─────────────────────────────────────────────────────────────────────────────
# Stores the unique request ID (cid) during request handling.
# Access via get_cid() to retrieve the current request's correlation ID.
request_cid: ContextVar[str | None] = ContextVar("request_cid", default=None)


def get_cid() -> str | None:
    """Get the current request's correlation ID.

    Returns None if called outside a request context.
    """
    return request_cid.get()


def set_cid(cid: str) -> None:
    """Set the correlation ID for the current request context."""
    request_cid.set(cid)


# ─────────────────────────────────────────────────────────────────────────────
# Custom JSON formatter with automatic context injection
# ─────────────────────────────────────────────────────────────────────────────
class ContextAwareJsonFormatter(JsonFormatter):
    """JSON formatter that automatically includes request context (cid).

    Injects correlation ID (cid) into every log record if available in context.
    This ensures all logs for a given request are linked via the same cid.
    """

    def add_fields(
        self,
        log_data: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add fields to log record, including automatic cid injection."""
        super().add_fields(log_data, record, message_dict)
        cid = get_cid()
        if cid:
            log_data["cid"] = cid


def setup_logging() -> logging.Logger:
    """Initialize structured JSON logging for the entire application.

    Call once at app startup (in lifespan hook or main).
    Returns the root logger configured for JSON output.
    Log level is controlled by the LOG_LEVEL environment variable (default: INFO).
    """
    level = logging.getLevelName(settings.log_level.upper())
    if not isinstance(level, int):
        level = logging.INFO

    # Use root logger so all child loggers inherit the formatter
    logger = logging.getLogger()

    # Only add handler if not already present (prevents duplication on reload)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ContextAwareJsonFormatter())
        logger.addHandler(handler)

    logger.setLevel(level)

    return logging.getLogger(__name__)
