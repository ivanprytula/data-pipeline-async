"""AI Gateway service — semantic search and embeddings.

Phase 3 of data-pipeline-async learning journey.

Submodules:
- embeddings: Lazy-loaded sentence transformer with LRU caching
- vector_store: Qdrant client wrapper for document indexing and search
- main: FastAPI app with health, embed, search, index endpoints
"""
