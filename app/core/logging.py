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


# ---------------------------------------------------------------------------
# AppLogger wrapper
# ---------------------------------------------------------------------------
class AppLogger:
    """Thin wrapper around a standard logging.Logger.

    Features:
    - Callable interface: `logger("event_name", level="debug", **extra)`
      where `level` may be a string like 'debug' or an int. If `level` is
      omitted, defaults to INFO.
    - Exposes standard logger methods (`debug`, `info`, `warning`, `error`,
      `exception`, `critical`) by delegating to the underlying logger so
      existing callsites continue to work.
    - Provides `set_level()` helper to change level at runtime.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def __call__(
        self, event: str, level: str | int | None = None, **extra: Any
    ) -> None:
        """Log an event using the provided level or INFO by default.

        The `event` is used as the message and also injected into `extra` as
        the `event` field for structured logging consumers.
        """
        if level is None:
            lvl = logging.INFO
        elif isinstance(level, int):
            lvl = level
        else:
            lvl = logging.getLevelName(str(level).upper())
            if not isinstance(lvl, int):
                lvl = logging.INFO

        extra_with_event = {"event": event}
        extra_with_event.update(extra)
        # Use Logger.log to support dynamic level values
        self._logger.log(lvl, event, extra=extra_with_event)

    def set_level(self, level: str | int) -> None:
        """Set the logger level at runtime."""
        if isinstance(level, int):
            lvl = level
        else:
            lvl = logging.getLevelName(str(level).upper())
            if not isinstance(lvl, int):
                lvl = logging.INFO
        self._logger.setLevel(lvl)

    def __getattr__(self, name: str):
        # Delegate attribute access to the underlying logger (info, debug, etc.)
        return getattr(self._logger, name)


def setup_logging() -> AppLogger:
    """Initialize structured JSON logging for the entire application.

    Call once at app startup (in lifespan hook or main).
    Returns the root logger configured for JSON output.
    Log level is controlled by the LOG_LEVEL environment variable (default: INFO).
    """
    # Resolve configured level (fall back to INFO for invalid values)
    configured = str(settings.log_level or "").upper()
    level = logging.getLevelName(configured)
    if not isinstance(level, int):
        level = logging.INFO

    # Use root logger so all child loggers inherit the formatter
    root_logger = logging.getLogger()

    # Only add handler if not already present (prevents duplication on reload)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ContextAwareJsonFormatter())
        root_logger.addHandler(handler)

    root_logger.setLevel(level)

    # Return an AppLogger wrapping a module-level logger so callsites keep
    # working with `logger.info(...)` and also gain callable-style logging.
    return AppLogger(logging.getLogger(__name__))
