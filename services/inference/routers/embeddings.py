"""Embedding endpoints: POST /embed and POST /embed-batch."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from ..embeddings import embed_batch, embed_text
from ..schemas import EmbedBatchRequest, EmbedBatchResponse, EmbedRequest, EmbedResponse


router = APIRouter(tags=["embeddings"])
logger = logging.getLogger(__name__)


@router.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    """Embed a single text.

    Args:
        request: Text to embed.

    Returns:
        Embedding vector and its dimension.
    """
    try:
        embedding = await embed_text(request.text)
        return EmbedResponse(embedding=embedding, dimension=len(embedding))
    except Exception as exc:
        logger.error("embed_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to embed text",
        ) from exc


@router.post("/embed-batch", response_model=EmbedBatchResponse)
async def embed_batch_endpoint(request: EmbedBatchRequest) -> EmbedBatchResponse:
    """Embed multiple texts in a single batch.

    Args:
        request: List of texts to embed (1–100).

    Returns:
        List of embedding vectors and count.
    """
    try:
        embeddings = await embed_batch(request.texts)
        return EmbedBatchResponse(embeddings=embeddings, count=len(embeddings))
    except Exception as exc:
        logger.error("embed_batch_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to embed batch",
        ) from exc
