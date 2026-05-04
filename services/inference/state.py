"""Module-level vector store singleton and FastAPI dependency."""

from __future__ import annotations

from fastapi import HTTPException, status

from .vector_store import VectorStore


# Populated by main.py lifespan startup; read by routers via get_vector_store()
_instance: VectorStore | None = None


def set_vector_store(vs: VectorStore) -> None:
    """Set the module-level VectorStore singleton (called from lifespan)."""
    global _instance
    _instance = vs


def get_vector_store() -> VectorStore:
    """FastAPI dependency — return the initialised VectorStore or raise 503."""
    if _instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store not initialized",
        )
    return _instance
