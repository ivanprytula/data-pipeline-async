"""Structured JSON logging setup — runs once at app startup."""

import logging

from pythonjsonlogger.json import JsonFormatter


def setup_logging() -> logging.Logger:
    """Initialize structured JSON logging for the entire application.

    Call once at app startup (in lifespan hook or main).
    Returns the root logger configured for JSON output.
    """
    # Use root logger so all child loggers inherit the formatter
    logger = logging.getLogger()

    # Only add handler if not already present (prevents duplication on reload)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logging.getLogger(__name__)
