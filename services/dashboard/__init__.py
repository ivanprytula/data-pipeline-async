"""Dashboard service — server-rendered HTMX UI.

Entry point: ``uvicorn services.dashboard.main:app``

Pages:
- /        Records Explorer (HTMX infinite scroll, calls ingestor)
- /search  Semantic Search (calls inference /search)
- /metrics Live Metrics (SSE stream from ingestor /metrics)

Key submodules:
- main: FastAPI app, lifespan hook, static files, template mounts
- http_client: shared httpx.AsyncClient for upstream service calls
- routers/pages: page route handlers
- routers/sse: Server-Sent Events endpoint for live metrics
"""
