"""Inference service — text embeddings and semantic vector search.

Entry point: ``uvicorn services.inference.main:app``

Key submodules:
- embeddings: lazy-loaded sentence transformer with LRU caching
- vector_store: Qdrant client wrapper for document indexing and search
- schemas: Pydantic v2 request/response schemas
- main: FastAPI app with /health, /embed, /search, /index endpoints
"""
