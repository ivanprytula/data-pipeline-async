"""FastAPI dependencies for query_api.

Re-exports ``get_db`` from ``database`` so that routers retain a stable
import path (``services.query_api.dependencies.get_db``) independent of
where the implementation lives.
"""

from .database import get_db as get_db  # noqa: F401
