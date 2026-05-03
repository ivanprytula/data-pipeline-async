"""Dashboard service constants."""

from __future__ import annotations

import os


DEFAULT_PAGE_SIZE: int = 50
INGESTOR_URL: str = os.getenv("INGESTOR_URL", "http://localhost:8000")
READYZ_CACHE_TTL: float = 5.0
