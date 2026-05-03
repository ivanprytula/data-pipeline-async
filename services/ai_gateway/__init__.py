"""AI Gateway service — text embeddings and semantic vector search.

Entry point: ``uvicorn services.ai_gateway.main:app``

Key submodules:
- embeddings: lazy-loaded sentence transformer with LRU caching
- vector_store: Qdrant client wrapper for document indexing and search
- schemas: Pydantic v2 request/response schemas
- main: FastAPI app with /health, /embed, /search, /index endpoints

Note: will be renamed to ``services.inference`` in Phase 2 restructure.
"""
