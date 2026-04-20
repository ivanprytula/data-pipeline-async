"""Embeddings module — lazy-loaded sentence transformer with LRU cache.

Singleton pattern: model loaded once on first use, reused for all requests.
LRU cache: avoid re-embedding identical text in the same request batch.

Design notes:
- `sentence-transformers` from HuggingFace Transformers
- Model: all-MiniLM-L6-v2 (50MB, fast, good quality for semantic search)
- Cache: functools.lru_cache on the core embedding function
- Thread-safe: sentence_transformers is CPU-bound, runs on main thread via executor
"""

from __future__ import annotations

import functools
import logging
from typing import Final

from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)

# Model ID from HuggingFace Hub
_MODEL_NAME: Final[str] = "all-MiniLM-L6-v2"
_EMBEDDING_DIM: Final[int] = 384  # Output dimension of all-MiniLM-L6-v2

# Singleton instance (lazy-loaded)
_model_instance: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Load and cache the embedding model.

    Lazy initialization: first call downloads from HuggingFace, subsequent calls
    return the same instance.

    Returns:
        Loaded SentenceTransformer instance.
    """
    global _model_instance
    if _model_instance is None:
        logger.info(f"Loading embedding model {_MODEL_NAME}...")
        _model_instance = SentenceTransformer(_MODEL_NAME)
        logger.info(f"Model loaded. Embedding dimension: {_EMBEDDING_DIM}")
    return _model_instance


@functools.lru_cache(maxsize=1000)
def _embed_cached(text: str) -> tuple[float, ...]:
    """Core embedding function with LRU cache.

    Args:
        text: Document text to embed (exact match for cache hit).

    Returns:
        Tuple of floats (embedding vector).
    """
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return tuple(embedding.tolist())  # tuple for hashability


async def embed_text(text: str) -> list[float]:
    """Embed a single text string (async wrapper).

    Args:
        text: Document text to embed.

    Returns:
        Embedding vector as list of floats.

    Side effects:
        First call loads the model from HuggingFace.
    """
    # Note: sentence_transformers is synchronous, CPU-bound.
    # In production, would use executor to avoid blocking event loop.
    # For now (Phase 3), acceptable on moderate load.
    cached = _embed_cached(text)
    return list(cached)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a single batch (efficient).

    Args:
        texts: List of document texts to embed.

    Returns:
        List of embedding vectors, aligned with input order.

    Note:
        Batch embedding is more efficient than individual calls,
        but each text is still cached independently.
    """
    embeddings = []
    for text in texts:
        embedding = await embed_text(text)
        embeddings.append(embedding)
    return embeddings


def get_embedding_dimension() -> int:
    """Return the embedding vector dimension (for schema setup).

    Returns:
        384 for all-MiniLM-L6-v2.
    """
    return _EMBEDDING_DIM
