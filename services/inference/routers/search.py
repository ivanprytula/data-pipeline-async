"""Search endpoints: POST /index and POST /search."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..embeddings import embed_batch, embed_text
from ..filters import dict_to_qdrant_filter
from ..schemas import (
    IndexRequest,
    IndexResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from ..state import get_vector_store
from ..vector_store import VectorStore


router = APIRouter(tags=["search"])
logger = logging.getLogger(__name__)

type VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]


@router.post("/index", response_model=IndexResponse)
async def index(request: IndexRequest, vs: VectorStoreDep) -> IndexResponse:
    """Index documents — upsert embeddings to Qdrant.

    Each document must have ``id`` (int), ``text`` (str), and optionally
    ``metadata`` (dict).

    Args:
        request: Documents to index and target collection name.
        vs: Injected VectorStore dependency.

    Returns:
        Count of indexed documents and collection name.
    """
    try:
        vs.ensure_collection(request.collection)
        texts = [doc["text"] for doc in request.documents]
        embeddings = await embed_batch(texts)
        points = [
            (
                doc["id"],
                embeddings[i],
                {"text": doc["text"], **(doc.get("metadata", {}))},
            )
            for i, doc in enumerate(request.documents)
        ]
        vs.upsert_points(request.collection, points)
        logger.info(
            "documents_indexed",
            extra={"count": len(request.documents), "collection": request.collection},
        )
        return IndexResponse(
            indexed_count=len(request.documents), collection=request.collection
        )
    except Exception as exc:
        logger.error("index_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to index documents",
        ) from exc


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, vs: VectorStoreDep) -> SearchResponse:
    """Semantic similarity search.

    Args:
        request: Query text, top-k count, collection name, and optional filters.
        vs: Injected VectorStore dependency.

    Returns:
        Ranked list of matching documents.
    """
    try:
        query_embedding = await embed_text(request.query)
        qdrant_filters = dict_to_qdrant_filter(request.filters)
        results = vs.search(
            collection_name=request.collection,
            query_vector=query_embedding,
            top_k=request.top_k,
            filters=qdrant_filters,
        )
        search_results = [
            SearchResult(id=r["id"], score=r["score"], metadata=r["metadata"])
            for r in results
        ]
        logger.info(
            "search_complete",
            extra={"query": request.query, "results": len(search_results)},
        )
        return SearchResponse(
            results=search_results,
            count=len(search_results),
            query=request.query,
        )
    except Exception as exc:
        logger.error("search_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        ) from exc
