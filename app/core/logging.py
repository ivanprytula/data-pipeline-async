"""Structured JSON logging setup — runs once at app startup."""

import logging

from pythonjsonlogger.json import JsonFormatter

from app.config import settings


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
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    logger.setLevel(level)

    return logging.getLogger(__name__)
