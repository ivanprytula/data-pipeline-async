"""Internal service-to-service JWT authentication.

Provides token generation and verification for M2M calls within the data-zoo
cluster. All services share a single INTERNAL_JWT_SECRET (from Secrets Manager).

Token claims:
- iss: "data-zoo-internal"
- sub: <service-name>
- exp: now + 60 seconds (short-lived; refreshed on each outbound request)
- iat: issued-at timestamp

Usage — outbound request (service making the call):

    from libs.platform.auth import generate_internal_token
    import httpx

    headers = {"Authorization": f"Bearer {generate_internal_token('ingestor')}"}
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://inference:8001/api/v1/embed", headers=headers)

Usage — inbound route (service receiving the call):

    from libs.platform.auth import InternalAuthDep

    @router.post("/admin/trigger-replay")
    async def trigger_replay(claims: InternalAuthDep) -> dict:
        ...

FastAPI dependency:

    type InternalAuthDep = Annotated[ServiceClaims, Depends(require_internal_auth)]
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel


logger = logging.getLogger(__name__)

_ISSUER = "data-zoo-internal"
_TOKEN_TTL_SECONDS = 60
_ALGORITHM = "HS256"


def _get_secret() -> str:
    """Read INTERNAL_JWT_SECRET from environment.

    Returns:
        Secret string for JWT signing/verification.

    Raises:
        RuntimeError: If INTERNAL_JWT_SECRET is not configured.
    """
    secret = os.environ.get("INTERNAL_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "INTERNAL_JWT_SECRET is not set. "
            "Configure it via environment variable or Secrets Manager."
        )
    return secret


class ServiceClaims(BaseModel):
    """Validated claims from an internal JWT token.

    Attributes:
        sub: Name of the calling service (e.g., "ingestor", "processor").
        iss: Must be "data-zoo-internal".
        exp: Expiry timestamp (validated by PyJWT).
        iat: Issued-at timestamp.
    """

    sub: str
    iss: str
    exp: int
    iat: int


def generate_internal_token(service_name: str) -> str:
    """Generate a short-lived internal JWT for service-to-service calls.

    Args:
        service_name: Logical name of the calling service (e.g., "ingestor").

    Returns:
        Signed JWT string. Valid for _TOKEN_TTL_SECONDS seconds.

    Raises:
        RuntimeError: If INTERNAL_JWT_SECRET is not configured.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": _ISSUER,
        "sub": service_name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=_TOKEN_TTL_SECONDS)).timestamp()),
    }
    token = jwt.encode(payload, _get_secret(), algorithm=_ALGORITHM)
    return token


def verify_internal_token(token: str) -> ServiceClaims:
    """Verify and decode an internal JWT.

    Args:
        token: Raw JWT string (without "Bearer " prefix).

    Returns:
        Decoded ServiceClaims.

    Raises:
        jwt.ExpiredSignatureError: If token has expired.
        jwt.InvalidTokenError: If token is invalid (wrong secret, issuer, algorithm).
    """
    payload = jwt.decode(
        token,
        _get_secret(),
        algorithms=[_ALGORITHM],
        options={"require": ["iss", "sub", "exp", "iat"]},
    )

    if payload.get("iss") != _ISSUER:
        raise jwt.InvalidIssuerError(
            f"Invalid issuer: expected '{_ISSUER}', got '{payload.get('iss')}'"
        )

    return ServiceClaims(**payload)


async def require_internal_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> ServiceClaims:
    """FastAPI dependency: verify internal JWT from Authorization header.

    Args:
        authorization: Value of the Authorization header (injected by FastAPI).

    Returns:
        Validated ServiceClaims if token is valid.

    Raises:
        HTTPException 401: If header is missing, malformed, or token is invalid/expired.
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header for internal endpoint",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme",
        )

    raw_token = authorization.removeprefix("Bearer ")

    try:
        claims = verify_internal_token(raw_token)
    except jwt.ExpiredSignatureError:
        logger.warning("internal_token_expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Internal token has expired",
        ) from None
    except jwt.InvalidTokenError as exc:
        logger.warning("internal_token_invalid", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal token",
        ) from exc

    return claims


# FastAPI Annotated type alias for use in route signatures.
type InternalAuthDep = Annotated[ServiceClaims, Depends(require_internal_auth)]
