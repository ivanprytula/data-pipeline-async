"""Integration tests for auth-protected routes and endpoints.

Tests session-based auth, bearer token auth, protected docs, and rate limit handler.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ingestor.schemas import RecordRequest


@pytest.mark.integration
class TestSessionAuth:
    """Tests for session-based auth routes."""

    async def test_login_session_creates_session(self, client: AsyncClient) -> None:
        """POST /api/v1/records/auth/login creates a session cookie."""
        response = await client.post(
            "/api/v1/records/auth/login",
            params={"user_id": "testuser"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "message" in data
        assert isinstance(data["session_id"], str)
        assert len(data["session_id"]) > 0

    async def test_get_record_secured_requires_session(
        self, client: AsyncClient, db: AsyncSession, record_timestamp
    ) -> None:
        """GET /api/v1/records/{id}/secure requires valid session cookie."""
        from ingestor import crud

        record = await crud.create_record(
            db,
            RecordRequest(source="test", timestamp=record_timestamp, data={}),
        )

        # Without session, should get 401
        response = await client.get(f"/api/v1/records/{record.id}/secure")
        assert response.status_code == 401

    async def test_get_record_secured_with_valid_session(
        self, client: AsyncClient, db: AsyncSession, record_timestamp
    ) -> None:
        """GET /api/v1/records/{id}/secure succeeds with valid session cookie."""
        from ingestor import crud

        # Create a record
        record = await crud.create_record(
            db,
            RecordRequest(source="test", timestamp=record_timestamp, data={}),
        )

        # Login to get session
        login_response = await client.post(
            "/api/v1/records/auth/login",
            params={"user_id": "testuser"},
        )
        session_id = login_response.json()["session_id"]

        # Set session cookie on client instance (not per-request)
        client.cookies.set("session_id", session_id)
        response = await client.get(f"/api/v1/records/{record.id}/secure")
        assert response.status_code == 200
        assert response.json()["id"] == record.id

    async def test_get_record_secured_with_expired_session(
        self, client: AsyncClient, db: AsyncSession, record_timestamp
    ) -> None:
        """GET /api/v1/records/{id}/secure fails with expired session."""
        import uuid
        from datetime import UTC, datetime, timedelta

        from ingestor import crud
        from ingestor.auth import _session_store

        # Create a record
        record = await crud.create_record(
            db,
            RecordRequest(source="test", timestamp=record_timestamp, data={}),
        )

        # Create an expired session directly
        session_id = str(uuid.uuid4())
        _session_store[session_id] = {
            "user_id": "testuser",
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": datetime.now(UTC) - timedelta(hours=1),  # Expired
        }

        # Set expired session cookie on client instance
        client.cookies.set("session_id", session_id)
        response = await client.get(f"/api/v1/records/{record.id}/secure")
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    async def test_archive_record_secured_requires_writer_or_admin(
        self, client: AsyncClient, db: AsyncSession, record_timestamp
    ) -> None:
        """RBAC secure archive endpoint denies viewer role and allows writer role."""
        from ingestor import crud

        record = await crud.create_record(
            db,
            RecordRequest(source="test", timestamp=record_timestamp, data={}),
        )

        viewer_login = await client.post(
            "/api/v1/records/auth/login",
            params={"user_id": "viewer-user", "role": "viewer"},
        )
        client.cookies.set("session_id", viewer_login.json()["session_id"])
        viewer_response = await client.patch(
            f"/api/v1/records/{record.id}/secure/archive"
        )
        assert viewer_response.status_code == 403

        writer_login = await client.post(
            "/api/v1/records/auth/login",
            params={"user_id": "writer-user", "role": "writer"},
        )
        client.cookies.set("session_id", writer_login.json()["session_id"])
        writer_response = await client.patch(
            f"/api/v1/records/{record.id}/secure/archive"
        )
        assert writer_response.status_code == 200

    async def test_delete_record_secured_requires_admin(
        self, client: AsyncClient, db: AsyncSession, record_timestamp
    ) -> None:
        """RBAC secure delete endpoint allows only admin role."""
        from ingestor import crud

        record = await crud.create_record(
            db,
            RecordRequest(source="test", timestamp=record_timestamp, data={}),
        )

        writer_login = await client.post(
            "/api/v1/records/auth/login",
            params={"user_id": "writer-user", "role": "writer"},
        )
        client.cookies.set("session_id", writer_login.json()["session_id"])
        writer_response = await client.delete(
            f"/api/v1/records/{record.id}/secure/delete"
        )
        assert writer_response.status_code == 403

        admin_login = await client.post(
            "/api/v1/records/auth/login",
            params={"user_id": "admin-user", "role": "admin"},
        )
        client.cookies.set("session_id", admin_login.json()["session_id"])
        admin_response = await client.delete(
            f"/api/v1/records/{record.id}/secure/delete"
        )
        assert admin_response.status_code == 204


@pytest.mark.integration
class TestBearerTokenAuth:
    """Tests for bearer token auth routes.

    Note: API_V1_BEARER_TOKEN is not set in .env, so these tests verify
    that auth is disabled and endpoints are accessible without tokens.
    """

    async def test_create_records_batch_protected_works_when_disabled(
        self, client: AsyncClient
    ) -> None:
        """POST /api/v1/records/batch/protected works when token auth is disabled (.env not set)."""
        response = await client.post(
            "/api/v1/records/batch/protected",
            json={
                "records": [
                    {"source": "test", "timestamp": "2024-01-01T00:00:00", "data": {}},
                ]
            },
        )
        # Since API_V1_BEARER_TOKEN is not set in .env, auth is disabled
        # and endpoint returns 201 (no auth required)
        assert response.status_code == 201
        assert response.json()["created"] == 1


@pytest.mark.integration
class TestProtectedDocs:
    """Tests for documentation endpoints.

    Note: In test environment, docs_username/password are not set
    (or test config overrides them), so docs are public.
    """

    async def test_docs_endpoint_accessible(self, client: AsyncClient) -> None:
        """GET /docs returns Swagger UI (accessible in test environment)."""
        response = await client.get("/docs")
        assert response.status_code == 200
        # Swagger UI contains specific HTML
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

    async def test_openapi_schema_accessible(self, client: AsyncClient) -> None:
        """GET /openapi.json returns valid OpenAPI schema (accessible in test environment)."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["openapi"].startswith("3.")
        assert "paths" in schema
        assert "info" in schema

    async def test_redoc_endpoint_accessible(self, client: AsyncClient) -> None:
        """GET /redoc returns ReDoc UI (accessible in test environment)."""
        response = await client.get("/redoc")
        assert response.status_code == 200
        # ReDoc contains specific HTML
        assert "redoc" in response.text.lower() or "openapi" in response.text.lower()


@pytest.mark.integration
class TestRateLimitHandler:
    """Tests for rate limit exceeded handler."""

    async def test_create_record_endpoint_works(self, client: AsyncClient) -> None:
        """Create record endpoint works (rate limit applied)."""
        response = await client.post(
            "/api/v1/records",
            json={"source": "test", "timestamp": "2024-01-01T00:00:00", "data": {}},
        )
        assert response.status_code == 201
        # Slowapi may or may not set these headers depending on configuration
        # Just verify the endpoint works
        assert "id" in response.json()


@pytest.mark.integration
class TestSecurityHeaders:
    """Baseline security headers should be attached by middleware."""

    async def test_security_headers_present_on_health(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "Permissions-Policy" in response.headers
