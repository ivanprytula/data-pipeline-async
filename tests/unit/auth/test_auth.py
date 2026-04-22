"""Unit tests for all authentication layers in app/auth.py.

Covers:
- Layer 1: Docs auth (HTTP Basic)
- Layer 2: Bearer token + session cookie
- Layer 3: JWT create/verify
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

import ingestor.auth as auth_module
from ingestor.auth import (
    create_jwt_token,
    create_session,
    verify_bearer_token,
    verify_docs_credentials,
    verify_jwt_token,
    verify_session,
)


# ---------------------------------------------------------------------------
# Layer 1: Docs Auth (HTTP Basic)
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestDocsAuth:
    """HTTP Basic Auth for documentation endpoints."""

    async def test_valid_credentials_returns_credentials(self) -> None:
        """Correct username+password passes through unchanged."""
        creds = HTTPBasicCredentials(username="admin", password="secret")
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.docs_username = "admin"
            mock_settings.docs_password = "secret"
            result = await verify_docs_credentials(creds)
        assert result is creds

    async def test_wrong_username_raises_403(self) -> None:
        """Wrong username raises 403 Forbidden."""
        creds = HTTPBasicCredentials(username="hacker", password="secret")
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.docs_username = "admin"
            mock_settings.docs_password = "secret"
            with pytest.raises(HTTPException) as exc:
                await verify_docs_credentials(creds)
        assert exc.value.status_code == 403

    async def test_wrong_password_raises_403(self) -> None:
        """Wrong password raises 403 Forbidden."""
        creds = HTTPBasicCredentials(username="admin", password="wrongpass")
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.docs_username = "admin"
            mock_settings.docs_password = "secret"
            with pytest.raises(HTTPException) as exc:
                await verify_docs_credentials(creds)
        assert exc.value.status_code == 403

    async def test_auth_disabled_passes_through(self) -> None:
        """When docs_username is not set, any credentials pass through."""
        creds = HTTPBasicCredentials(username="anyone", password="anything")
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.docs_username = None
            mock_settings.docs_password = None
            result = await verify_docs_credentials(creds)
        assert result is creds


# ---------------------------------------------------------------------------
# Layer 2: Bearer Token
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestBearerToken:
    """Bearer token auth for v1 API endpoints."""

    async def test_valid_token_returns_credentials(self) -> None:
        """Correct bearer token returns the token string."""
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.api_v1_bearer_token = "secret-token"
            result = await verify_bearer_token("Bearer secret-token")
        assert result == "secret-token"

    async def test_missing_header_raises_401(self) -> None:
        """No Authorization header raises 401."""
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.api_v1_bearer_token = "secret-token"
            with pytest.raises(HTTPException) as exc:
                await verify_bearer_token(None)
        assert exc.value.status_code == 401

    async def test_wrong_scheme_raises_401(self) -> None:
        """Non-Bearer scheme (e.g., Basic) raises 401."""
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.api_v1_bearer_token = "secret-token"
            with pytest.raises(HTTPException) as exc:
                await verify_bearer_token("Basic secret-token")
        assert exc.value.status_code == 401

    async def test_invalid_token_raises_403(self) -> None:
        """Wrong token value raises 403 Forbidden."""
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.api_v1_bearer_token = "secret-token"
            with pytest.raises(HTTPException) as exc:
                await verify_bearer_token("Bearer wrong-token")
        assert exc.value.status_code == 403

    async def test_auth_disabled_returns_public(self) -> None:
        """When api_v1_bearer_token is not set, any request returns 'public'."""
        with patch("ingestor.auth.settings") as mock_settings:
            mock_settings.api_v1_bearer_token = None
            result = await verify_bearer_token(None)
        assert result == "public"


# ---------------------------------------------------------------------------
# Layer 2: Session Cookie
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestSessionCookie:
    """Cookie-based session auth for v1 API endpoints."""

    async def test_valid_session_returns_data(self) -> None:
        """Valid non-expired session ID returns session data dict."""
        session_id, _ = create_session("user-42")
        result = await verify_session(session_id)

        assert result["user_id"] == "user-42"

    async def test_missing_cookie_raises_401(self) -> None:
        """No session_id cookie raises 401."""
        with pytest.raises(HTTPException) as exc:
            await verify_session(None)
        assert exc.value.status_code == 401

    async def test_unknown_session_raises_401(self) -> None:
        """Non-existent session ID raises 401."""
        with pytest.raises(HTTPException) as exc:
            await verify_session("00000000-0000-0000-0000-000000000000")
        assert exc.value.status_code == 401

    async def test_expired_session_raises_401(self) -> None:
        """Expired session is deleted and raises 401."""
        session_id, _ = create_session("user-99")
        # Manually expire the session
        auth_module._session_store[session_id]["expires_at"] = datetime(
            2000, 1, 1, tzinfo=UTC
        )
        with pytest.raises(HTTPException) as exc:
            await verify_session(session_id)
        assert exc.value.status_code == 401
        # Verify it was cleaned up from the store
        assert session_id not in auth_module._session_store

    async def test_create_session_stores_user_id(self) -> None:
        """create_session returns a session_id that maps to the correct user."""
        session_id, _ = create_session("user-123", {"role": "admin"})
        assert session_id in auth_module._session_store
        assert auth_module._session_store[session_id]["user_id"] == "user-123"
        assert auth_module._session_store[session_id]["role"] == "admin"


# ---------------------------------------------------------------------------
# Layer 3: JWT
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestJWT:
    """JWT create and verify for v2 API endpoints."""

    async def test_valid_token_returns_claims(self) -> None:
        """Valid JWT returns decoded payload with correct subject."""
        token = create_jwt_token("user-1")
        claims = await verify_jwt_token(f"Bearer {token}")

        assert claims["sub"] == "user-1"

    async def test_custom_claims_included(self) -> None:
        """Custom claims are preserved in the encoded token."""
        token = create_jwt_token("user-2", {"role": "admin", "tier": "pro"})
        claims = await verify_jwt_token(f"Bearer {token}")

        assert claims["role"] == "admin"
        assert claims["tier"] == "pro"

    async def test_missing_header_raises_401(self) -> None:
        """No Authorization header raises 401."""
        with pytest.raises(HTTPException) as exc:
            await verify_jwt_token(None)
        assert exc.value.status_code == 401

    async def test_wrong_scheme_raises_401(self) -> None:
        """Non-Bearer scheme raises 401."""
        token = create_jwt_token("user-3")
        with pytest.raises(HTTPException) as exc:
            await verify_jwt_token(f"Basic {token}")
        assert exc.value.status_code == 401

    async def test_expired_token_raises_401(self) -> None:
        """Expired JWT raises 401 with 'Token expired' detail."""
        from datetime import UTC

        import jwt as pyjwt

        from ingestor.config import settings

        expired_payload = {
            "sub": "user-4",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "iss": settings.app_name,
        }
        expired_token = pyjwt.encode(
            expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(HTTPException) as exc:
            await verify_jwt_token(f"Bearer {expired_token}")
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    async def test_tampered_token_raises_401(self) -> None:
        """Token with altered signature raises 401."""
        with pytest.raises(HTTPException) as exc:
            await verify_jwt_token(
                "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.invalidsig"
            )
        assert exc.value.status_code == 401

    async def test_malformed_token_raises_401(self) -> None:
        """Completely invalid token string raises 401."""
        with pytest.raises(HTTPException) as exc:
            await verify_jwt_token("Bearer not.a.jwt")
        assert exc.value.status_code == 401
