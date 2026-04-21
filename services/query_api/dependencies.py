"""Dependencies for query_api service.

This module provides FastAPI dependencies that are configured at app startup.
get_db() is set up in main.py during app initialization.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession


# Placeholder that will be properly bound at app startup
async def get_db() -> AsyncGenerator[AsyncSession]:
    """Database session dependency.

    This function is a placeholder and will be configured at app startup
    with the actual AsyncSessionLocal factory.
    """
    raise NotImplementedError("get_db dependency not configured at app startup")
