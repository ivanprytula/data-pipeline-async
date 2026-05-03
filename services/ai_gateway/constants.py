"""ai_gateway constants."""

from __future__ import annotations

import os


QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME: str = "documents"
