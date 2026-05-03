"""Pydantic request/response schemas for ai_gateway."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .constants import COLLECTION_NAME


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
