"""FastAPI dependencies for analytics.

Re-exports ``get_db`` from ``database`` so that routers retain a stable
import path (``services.analytics.dependencies.get_db``) independent of
where the implementation lives.
"""

from .database import get_db as get_db  # noqa: F401
