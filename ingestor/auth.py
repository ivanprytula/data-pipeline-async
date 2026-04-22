"""Authentication and authorization utilities.

Three auth patterns for learning:
1. Docs Auth (HTTP Basic Auth)
2. v1 API (Bearer Token + Cookie Session)
3. v2 API (JWT)
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ingestor.config import settings


logger = logging.getLogger(__name__)

# HTTP Basic Auth scheme (for docs only)
security = HTTPBasic()

# Module-level type aliases (FastAPI-approved pattern)
type DocsCredentialsDep = Annotated[HTTPBasicCredentials, Depends(security)]

# In-memory session store (production would use Redis/database)
_session_store: dict[str, dict[str, Any]] = {}

# Simple role names for RBAC learning examples.
DEFAULT_ROLE = "viewer"


# ============================================================================
# Layer 1: Docs Auth (HTTP Basic Auth)
# ============================================================================


async def verify_docs_credentials(
    credentials: DocsCredentialsDep,
) -> HTTPBasicCredentials:
    """Verify credentials for documentation access."""
    if not settings.docs_username or not settings.docs_password:
        return credentials

    if credentials.username != settings.docs_username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    if credentials.password != settings.docs_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials


# ============================================================================
# Layer 2: v1 API Auth (Bearer Token + Sessions)
# ============================================================================


async def verify_bearer_token(
    authorization: str | None = Header(None),
) -> str:
    """Verify v1 bearer token from Authorization header.

    Usage: @router.post("/endpoint", dependencies=[Depends(verify_bearer_token)])
    or: api_key: str = Depends(verify_bearer_token)
    """
    if not settings.api_v1_bearer_token:
        return "public"  # Auth disabled

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials != settings.api_v1_bearer_token:
        logger.warning("bearer_token_invalid", extra={"token_prefix": credentials[:10]})
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid bearer token",
        )

    return credentials


async def verify_session(
    session_id: str | None = Cookie(None),
) -> dict[str, Any]:
    """Verify session from cookie.

    Returns session data dict if valid, else raises 401.
    Usage: session: dict = Depends(verify_session)
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session cookie",
        )

    session_data = _session_store.get(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    expires_at = session_data.get("expires_at")
    if expires_at is None or expires_at < datetime.now(UTC):
        del _session_store[session_id]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        ) from None

    return session_data


def _normalize_roles(raw_roles: Any) -> set[str]:
    """Normalize role claims from str/list/tuple into a lowercase role set."""
    if raw_roles is None:
        return set()
    if isinstance(raw_roles, str):
        return {raw_roles.strip().lower()} if raw_roles.strip() else set()
    if isinstance(raw_roles, Iterable):
        roles = {str(role).strip().lower() for role in raw_roles if str(role).strip()}
        return roles
    return set()


def _extract_roles(claims_or_session: dict[str, Any]) -> set[str]:
    """Extract normalized roles from auth context.

    Supports `role` and `roles` fields for compatibility across session/JWT payloads.
    """
    roles = set()
    roles.update(_normalize_roles(claims_or_session.get("roles")))
    roles.update(_normalize_roles(claims_or_session.get("role")))
    if not roles and claims_or_session.get("scope") == "records:write":
        roles.add("writer")
    return roles


def require_roles(required_roles: set[str], current_roles: set[str]) -> None:
    """Raise 403 when the current role set does not satisfy RBAC requirements."""
    if not (required_roles & current_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role permissions",
        )


def session_role_guard(*required_roles: str):
    """Create a session-based RBAC dependency.

    Example:
        AdminSessionDep = Annotated[dict[str, Any], Depends(session_role_guard("admin"))]
    """
    normalized_required = {role.lower() for role in required_roles}

    async def _guard(
        session: dict[str, Any] = Depends(verify_session),
    ) -> dict[str, Any]:
        roles = _extract_roles(session)
        require_roles(normalized_required, roles)
        return session

    return _guard


def jwt_role_guard(*required_roles: str):
    """Create a JWT-based RBAC dependency.

    Example:
        WriterJwtDep = Annotated[dict[str, Any], Depends(jwt_role_guard("writer", "admin"))]
    """
    normalized_required = {role.lower() for role in required_roles}

    async def _guard(
        claims: dict[str, Any] = Depends(verify_jwt_token),
    ) -> dict[str, Any]:
        roles = _extract_roles(claims)
        require_roles(normalized_required, roles)
        return claims

    return _guard


def create_session(
    user_id: str, custom_data: dict[str, Any] | None = None
) -> tuple[str, str]:
    """Create session cookie. Returns (session_id, Set-Cookie header value).

    Production: Use Redis with expiry, signed cookies, or JWT.
    """
    import uuid

    session_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(hours=settings.token_expiry_hours)

    _session_store[session_id] = {
        "user_id": user_id,
        "role": DEFAULT_ROLE,
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": expires_at,
        **(custom_data or {}),
    }

    logger.info("session_created", extra={"user_id": user_id, "session_id": session_id})
    return session_id, session_id


# ============================================================================
# Layer 3: v2 API Auth (JWT)
# ============================================================================


def create_jwt_token(
    sub: str,
    custom_claims: dict[str, Any] | None = None,
) -> str:
    """Create JWT token.

    Args:
        sub: Subject (user ID or identifier)
        custom_claims: Additional claims to encode

    Returns:
        JWT token string

    Security note: In production, rotate secrets periodically.
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_expiry_minutes)

    payload = {
        "sub": sub,
        "iat": now,
        "exp": expires_at,
        "iss": settings.app_name,
        **(custom_claims or {}),
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    logger.info("jwt_token_created", extra={"sub": sub, "exp": expires_at.isoformat()})
    return token


async def verify_jwt_token(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Verify JWT from Authorization header.

    Returns decoded token claims if valid.
    Usage: claims: dict = Depends(verify_jwt_token)
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("jwt_expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from None
    except jwt.InvalidSignatureError:
        logger.warning("jwt_invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
        ) from None
    except jwt.DecodeError as e:
        logger.warning("jwt_decode_error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        ) from None
