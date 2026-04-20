"""AI Gateway — FastAPI service for semantic search and embeddings.

Exposes endpoints:
- POST /embed: Embed single text
- POST /embed-batch: Embed multiple texts
- POST /index: Upsert document embeddings to Qdrant
- POST /search: Semantic similarity search
- GET /health: Health check

Connects to:
- Qdrant (vector store, gRPC)
- Processor (queue for async document indexing)

Phase 3 learning goals:
- Async patterns for I/O-bound operations
- Integration with Qdrant vector database
- Batch processing for efficiency
- Error handling and observability
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from .embeddings import embed_batch, embed_text
from .vector_store import VectorStore


logger = logging.getLogger(__name__)

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "documents"  # Default collection for general documents


# Pydantic schemas
class EmbedRequest(BaseModel):
    """Request to embed a single text."""

    text: str = Field(..., min_length=1, description="Text to embed")


class EmbedResponse(BaseModel):
    """Embedding vector response."""

    embedding: list[float] = Field(..., description="Embedding vector")
    dimension: int = Field(..., description="Vector dimension")


class EmbedBatchRequest(BaseModel):
    """Request to embed multiple texts."""

    texts: list[str] = Field(
        ..., min_items=1, max_items=100, description="Texts to embed"
    )


class EmbedBatchResponse(BaseModel):
    """Batch embedding response."""

    embeddings: list[list[float]] = Field(..., description="Embedding vectors")
    count: int = Field(..., description="Number of embeddings returned")


class IndexRequest(BaseModel):
    """Request to index documents in Qdrant."""

    documents: list[dict[str, Any]] = Field(
        ...,
        min_items=1,
        max_items=1000,
        description="Documents: [{'id': int, 'text': str, 'metadata': dict}, ...]",
    )
    collection: str = Field(
        default=COLLECTION_NAME, description="Target Qdrant collection"
    )


class IndexResponse(BaseModel):
    """Indexing response."""

    indexed_count: int = Field(..., description="Number of documents indexed")
    collection: str = Field(..., description="Collection name")


class SearchRequest(BaseModel):
    """Request to search for similar documents."""

    query: str = Field(..., min_length=1, description="Search query text")
    top_k: int = Field(
        default=5, ge=1, le=100, description="Number of results to return"
    )
    collection: str = Field(default=COLLECTION_NAME, description="Collection to search")
    filters: dict[str, Any] | None = Field(
        default=None, description="Optional metadata filters"
    )


class SearchResult(BaseModel):
    """Single search result."""

    id: int = Field(..., description="Document ID")
    score: float = Field(..., description="Similarity score (0-1, higher=better)")
    metadata: dict[str, Any] = Field(..., description="Document metadata")


class SearchResponse(BaseModel):
    """Search results response."""

    results: list[SearchResult] = Field(..., description="Matching documents")
    count: int = Field(..., description="Number of results")
    query: str = Field(..., description="Original query text")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="ok", description="Service status")
    qdrant_connected: bool = Field(..., description="Qdrant connection status")


# Global vector store (initialized in lifespan)
vector_store: VectorStore | None = None


def dict_to_qdrant_filter(filter_dict: dict[str, Any] | None) -> Filter | None:
    """Convert client filter dict to Qdrant Filter object.

    Supports nested structures with 'must', 'must_not', 'should' conditions.

    Expected format:
    {
        "must": [{"key": "source", "match": "api_docs"}],
        "must_not": [{"key": "archived", "match": True}],
        "should": [{"key": "timestamp", "range": {"gte": 1000000}}]
    }

    Args:
        filter_dict: Client filter dict or None.

    Returns:
        Qdrant Filter or None if no conditions.
    """
    if not filter_dict:
        return None

    conditions = []

    # Process 'must' conditions (AND logic)
    if "must" in filter_dict:
        for cond in filter_dict["must"]:
            conditions.append(_build_field_condition(cond))

    # Process 'must_not' conditions (NOT logic)
    if "must_not" in filter_dict:
        for cond in filter_dict["must_not"]:
            conditions.append(_build_field_condition(cond))

    # Process 'should' conditions (OR logic)
    if "should" in filter_dict:
        for cond in filter_dict["should"]:
            conditions.append(_build_field_condition(cond))

    if not conditions:
        return None

    # Combine all conditions with AND (must)
    result_filter = conditions[0]
    for cond in conditions[1:]:
        result_filter &= cond

    return result_filter


def _build_field_condition(condition_dict: dict[str, Any]) -> FieldCondition:
    """Build single FieldCondition from client condition dict.

    Supports: match (exact value), range (gte, lte, gt, lt).

    Args:
        condition_dict: {"key": "field_name", "match": value | "range": {"gte": ...}}

    Returns:
        Qdrant FieldCondition.
    """
    key = condition_dict.get("key")
    if not key:
        raise ValueError("Filter condition must have 'key' field")

    if "match" in condition_dict:
        # Exact match
        return FieldCondition(
            key=key,
            match=MatchValue(value=condition_dict["match"]),
        )

    if "range" in condition_dict:
        # Range query
        range_spec = condition_dict["range"]
        return FieldCondition(
            key=key,
            range=Range(
                gte=range_spec.get("gte"),
                lte=range_spec.get("lte"),
                gt=range_spec.get("gt"),
                lt=range_spec.get("lt"),
            ),
        )

    raise ValueError(f"Unsupported filter condition: {condition_dict}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, cleanup on shutdown."""
    global vector_store

    # Startup
    logger.info("AI Gateway starting...")
    try:
        vs = VectorStore(url=QDRANT_URL)
        vs.ensure_collection(COLLECTION_NAME)
        vector_store = vs
        logger.info("AI Gateway ready")
    except Exception as e:
        logger.error(f"Failed to initialize AI Gateway: {e}")
        raise

    yield

    # Shutdown
    logger.info("AI Gateway shutting down...")


# FastAPI app
app = FastAPI(
    title="AI Gateway",
    description="Semantic search and embeddings service (Phase 3)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    if not vector_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store not initialized",
        )
    return HealthResponse(status="ok", qdrant_connected=True)


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    """Embed a single text.

    Args:
        request: Text to embed.

    Returns:
        Embedding vector.
    """
    try:
        embedding = await embed_text(request.text)
        return EmbedResponse(embedding=embedding, dimension=len(embedding))
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to embed text",
        ) from e


@app.post("/embed-batch", response_model=EmbedBatchResponse)
async def embed_batch_endpoint(request: EmbedBatchRequest) -> EmbedBatchResponse:
    """Embed multiple texts in a batch.

    Args:
        request: Texts to embed.

    Returns:
        List of embedding vectors.
    """
    try:
        embeddings = await embed_batch(request.texts)
        return EmbedBatchResponse(embeddings=embeddings, count=len(embeddings))
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to embed batch",
        ) from e


@app.post("/index", response_model=IndexResponse)
async def index(request: IndexRequest) -> IndexResponse:
    """Index documents (upsert embeddings to Qdrant).

    Args:
        request: Documents with IDs, text, and metadata.

    Returns:
        Count of indexed documents.

    Note:
        - Each document must have: id (int), text (str), metadata (dict)
        - Text is embedded and stored with metadata in Qdrant
        - Collection is created if not exists
    """
    if not vector_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store not initialized",
        )

    try:
        # Ensure collection exists
        vector_store.ensure_collection(request.collection)

        # Extract texts and embed
        texts = [doc["text"] for doc in request.documents]
        embeddings = await embed_batch(texts)

        # Prepare points for Qdrant
        points = [
            (
                doc["id"],
                embeddings[i],
                {
                    "text": doc["text"],
                    **(doc.get("metadata", {})),  # Merge metadata
                },
            )
            for i, doc in enumerate(request.documents)
        ]

        # Upsert to Qdrant
        vector_store.upsert_points(request.collection, points)

        logger.info(
            f"Indexed {len(request.documents)} documents to '{request.collection}'"
        )
        return IndexResponse(
            indexed_count=len(request.documents), collection=request.collection
        )
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to index documents",
        ) from e


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """Semantic similarity search.

    Args:
        request: Query text, collection, top_k, optional filters.

    Returns:
        List of matching documents ranked by similarity.
    """
    if not vector_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store not initialized",
        )

    try:
        # Embed query
        query_embedding = await embed_text(request.query)

        # Convert filters from dict to Qdrant Filter
        qdrant_filters = dict_to_qdrant_filter(request.filters)

        # Search Qdrant
        results = vector_store.search(
            collection_name=request.collection,
            query_vector=query_embedding,
            top_k=request.top_k,
            filters=qdrant_filters,
        )

        # Format response
        search_results = [
            SearchResult(id=r["id"], score=r["score"], metadata=r["metadata"])
            for r in results
        ]

        logger.info(
            f"Search query '{request.query}' returned {len(search_results)} results"
        )
        return SearchResponse(
            results=search_results,
            count=len(search_results),
            query=request.query,
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        ) from e


if __name__ == "__main__":
    import uvicorn

    # Development server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )
