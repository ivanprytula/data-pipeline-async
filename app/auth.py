"""Authentication and authorization utilities."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings

# HTTP Basic Auth scheme
security = HTTPBasic()


async def verify_docs_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
) -> HTTPBasicCredentials:
    """Verify credentials for documentation access.

    Args:
        credentials: HTTP Basic Auth credentials (username, password)

    Returns:
        credentials if valid

    Raises:
        HTTPException: 403 Forbidden if credentials are invalid or not configured

    Examples:
        @app.get("/docs", dependencies=[Depends(verify_docs_credentials)])
        async def get_docs():
            ...
    """
    # If docs auth is disabled (no credentials configured), allow access
    if not settings.docs_username or not settings.docs_password:
        return credentials

    # Check username
    if credentials.username != settings.docs_username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Check password
    if credentials.password != settings.docs_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials
