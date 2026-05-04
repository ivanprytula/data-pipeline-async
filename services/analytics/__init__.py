"""Analytics service — read-side CQRS, analytics and materialized views.

Entry point: ``uvicorn services.analytics.main:app``

Key submodules:
- routers/analytics: window functions, aggregations, time-series queries
- database: read-only AsyncSession against the shared Postgres replica
- dependencies: get_db dependency injection
"""
