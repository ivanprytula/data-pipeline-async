"""Query API service — read-side CQRS, analytics and materialized views.

Entry point: ``uvicorn services.query_api.main:app``

Key submodules:
- routers/analytics: window functions, aggregations, time-series queries
- database: read-only AsyncSession against the shared Postgres replica
- dependencies: get_db dependency injection

Note: will be renamed to ``services.analytics`` in Phase 2 restructure.
"""
