"""AI Gateway — FastAPI service for semantic search and embeddings.

Entry point: ``uvicorn services.inference.main:app``

Connects to:
- Qdrant (vector store)
- SentenceTransformer (local, lazy-loaded)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from libs.platform.logging import setup_json_logger

from .constants import COLLECTION_NAME, QDRANT_URL
from .routers import embeddings as embeddings_router
from .routers import ops as ops_router
from .routers import search as search_router
from .state import set_vector_store
from .vector_store import VectorStore


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Initialise and shut down service-level resources."""
    setup_json_logger("inference")
    logger.info("inference_starting")
    try:
        vs = VectorStore(url=QDRANT_URL)
        vs.ensure_collection(COLLECTION_NAME)
        set_vector_store(vs)
        logger.info("inference_ready")
    except Exception as exc:
        logger.error("inference_init_failed", extra={"error": str(exc)})
        raise

    yield

    logger.info("inference_shutting_down")


app = FastAPI(
    title="AI Gateway",
    description="Semantic search and embeddings service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ops_router.router)
app.include_router(embeddings_router.router)
app.include_router(search_router.router)
