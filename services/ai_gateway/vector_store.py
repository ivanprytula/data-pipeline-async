"""Vector store client for Qdrant — collection creation, indexing, retrieval.

Responsibilities:
- Initialize connection to Qdrant via gRPC (port 6333)
- Create/verify collections for each document type
- Upsert points (embeddings + metadata)
- Perform similarity search with optional metadata filtering

Design notes:
- Qdrant gRPC client: high throughput, efficient binary protocol
- Collections: one per document source (e.g., "user_guides", "api_docs")
- Points: vector + optional metadata (doc_id, source, timestamp, etc.)
- Search: similarity-only or with metadata filters (e.g., source="api_docs")
"""

from __future__ import annotations

import logging
from typing import Any, Final
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http.models.models import QueryResponse
from qdrant_client.models import (
    Distance,
    Filter,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from .embeddings import get_embedding_dimension


logger = logging.getLogger(__name__)

# Qdrant connection
_QDRANT_URL: Final[str] = "http://localhost:6333"  # Set via env var in production
_QDRANT_TIMEOUT: Final[int] = 10  # seconds


class VectorStore:
    """Qdrant client wrapper for document indexing and retrieval."""

    def __init__(self, url: str = _QDRANT_URL) -> None:
        """Initialize Qdrant client.

        Args:
            url: Qdrant server URL (e.g., http://localhost:6333).
        """
        self.client: QdrantClient = QdrantClient(url=url)
        logger.info(f"Connected to Qdrant at {url}")

    def ensure_collection(
        self, collection_name: str, vector_size: int | None = None
    ) -> None:
        """Create collection if it doesn't exist.

        Args:
            collection_name: Name of the Qdrant collection.
            vector_size: Embedding dimension (defaults to model's 384).

        Side effects:
            Creates collection or logs if already exists.
        """
        if vector_size is None:
            vector_size = get_embedding_dimension()

        try:
            # Check if collection exists
            self.client.get_collection(collection_name)
            logger.info(f"Collection '{collection_name}' already exists")
        except Exception:
            # Collection does not exist, create it
            logger.info(f"Creating collection '{collection_name}'...")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,  # Cosine similarity
                ),
            )
            logger.info(f"Collection '{collection_name}' created")

    def upsert_points(
        self,
        collection_name: str,
        embeddings: list[tuple[int, list[float], dict[str, Any]]],
    ) -> None:
        """Insert or update points in collection.

        Args:
            collection_name: Target Qdrant collection.
            embeddings: List of (point_id, vector, metadata) tuples.

        Side effects:
            Inserts/updates points in Qdrant.
        """
        points = [
            PointStruct(id=point_id, vector=vector, payload=metadata)
            for point_id, vector, metadata in embeddings
        ]
        self.client.upsert(
            collection_name=collection_name,
            points=points,
        )
        logger.debug(f"Upserted {len(points)} points to '{collection_name}'")

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filters: Filter | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic similarity search.

        Args:
            collection_name: Qdrant collection to search.
            query_vector: Query embedding vector.
            top_k: Number of results to return.
            filters: Optional Qdrant Filter for metadata filtering.

        Returns:
            List of results: [{"id": int, "score": float, "metadata": dict}, ...]
        """
        results: QueryResponse = self.client.query_points(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=filters,
            limit=top_k,
        )
        return [
            {
                "id": result.id,  # ty:ignore[unresolved-attribute]
                "score": result.score,  # ty:ignore[unresolved-attribute]
                "metadata": result.payload,  # ty:ignore[unresolved-attribute]
            }
            for result in results
        ]

    def delete_points(
        self, collection_name: str, point_ids: list[int | str | UUID]
    ) -> None:
        """Delete points from collection.

        Args:
            collection_name: Target collection.
            point_ids: List of point IDs to delete.

        Side effects:
            Removes points from Qdrant.
        """
        self.client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=point_ids),
        )
        logger.debug(f"Deleted {len(point_ids)} points from '{collection_name}'")

    def get_info(self, collection_name: str) -> dict[str, Any]:
        """Fetch collection metadata.

        Args:
            collection_name: Target collection.

        Returns:
            Collection info: {"points_count": int, ...}
        """
        info = self.client.get_collection(collection_name)
        return {
            "points_count": info.points_count,
            "vectors_count": getattr(info, "vectors_count", None),
        }
