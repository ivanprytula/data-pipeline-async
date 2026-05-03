"""Integration tests for POST /api/v1/webhooks/{source} and GET endpoints."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from services.webhook.core import secrets as secrets_module
from tests.integration.webhook.conftest import SAMPLE_PAYLOAD


@pytest.fixture(autouse=True)
def clear_secrets_cache():
    """Reset the in-memory secrets cache before each test."""
    secrets_module._cache._store.clear()
    yield
    secrets_module._cache._store.clear()


class TestReceiveWebhook:
    """POST /api/v1/webhooks/{source}"""

    async def test_happy_path_202(self, client: AsyncClient, registered_source):
        """Valid payload from a registered source returns 202 with event_id."""
        response = await client.post(
            f"/api/v1/webhooks/{registered_source.name}",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert "event_id" in body
        assert "delivery_id" in body
        assert body["is_duplicate"] is False

    async def test_unknown_source_503(self, client: AsyncClient):
        """Posting to an unknown / inactive source returns 503."""
        response = await client.post(
            "/api/v1/webhooks/nonexistent-source",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 503

    async def test_duplicate_delivery_id_409(
        self, client: AsyncClient, registered_source
    ):
        """Second request with the same X-Delivery-ID returns 409 Conflict."""
        delivery_id = "dedup-test-delivery-id"
        headers = {
            "Content-Type": "application/json",
            "X-Delivery-Id": delivery_id,
        }
        first = await client.post(
            f"/api/v1/webhooks/{registered_source.name}",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers=headers,
        )
        assert first.status_code == 202

        second = await client.post(
            f"/api/v1/webhooks/{registered_source.name}",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers=headers,
        )
        assert second.status_code == 409

    async def test_invalid_signature_401(self, client: AsyncClient, registered_source):
        """Payload with wrong HMAC signature returns 401 Unauthorized.

        We set WEBHOOK_SIGNING_KEY_TEST-SOURCE to a known value so the
        validator computes a real HMAC and compares against a bad value.
        """
        import os

        env_key = (
            f"WEBHOOK_SIGNING_KEY_{registered_source.name.upper().replace('-', '_')}"
        )
        with patch.dict(os.environ, {env_key: "correct-secret"}):
            response = await client.post(
                f"/api/v1/webhooks/{registered_source.name}",
                content=json.dumps(SAMPLE_PAYLOAD),
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": "badhash" + "0" * 57,
                },
            )
        assert response.status_code == 401

    async def test_valid_signature_accepted(
        self, client: AsyncClient, registered_source
    ):
        """Payload with correct HMAC-SHA256 signature is accepted."""
        import hashlib
        import hmac as hmac_lib
        import os

        signing_key = "test-signing-secret"
        body = json.dumps(SAMPLE_PAYLOAD).encode("utf-8")
        expected_sig = hmac_lib.new(
            signing_key.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

        env_key = (
            f"WEBHOOK_SIGNING_KEY_{registered_source.name.upper().replace('-', '_')}"
        )
        with patch.dict(os.environ, {env_key: signing_key}):
            response = await client.post(
                f"/api/v1/webhooks/{registered_source.name}",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": expected_sig,
                },
            )
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"

    async def test_invalid_json_400(self, client: AsyncClient, registered_source):
        """Malformed JSON body returns 400 Bad Request."""
        response = await client.post(
            f"/api/v1/webhooks/{registered_source.name}",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    async def test_custom_delivery_id_preserved(
        self, client: AsyncClient, registered_source
    ):
        """Supplied X-Delivery-Id is echoed back in the response."""
        delivery_id = "my-custom-delivery-id"
        response = await client.post(
            f"/api/v1/webhooks/{registered_source.name}",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers={
                "Content-Type": "application/json",
                "X-Delivery-Id": delivery_id,
            },
        )
        assert response.status_code == 202
        assert response.json()["delivery_id"] == delivery_id


class TestGetWebhookEvent:
    """GET /api/v1/webhooks/{source}/{delivery_id}"""

    async def test_get_existing_event(self, client: AsyncClient, registered_source):
        """Fetching by delivery_id returns the persisted event record."""
        delivery_id = "fetch-test-delivery-id"
        post_resp = await client.post(
            f"/api/v1/webhooks/{registered_source.name}",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers={
                "Content-Type": "application/json",
                "X-Delivery-Id": delivery_id,
            },
        )
        assert post_resp.status_code == 202

        get_resp = await client.get(
            f"/api/v1/webhooks/{registered_source.name}/{delivery_id}"
        )
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["delivery_id"] == delivery_id
        assert body["source"] == registered_source.name

    async def test_get_nonexistent_event_404(
        self, client: AsyncClient, registered_source
    ):
        """Fetching an unknown delivery_id returns 404."""
        response = await client.get(
            f"/api/v1/webhooks/{registered_source.name}/does-not-exist"
        )
        assert response.status_code == 404

    async def test_get_wrong_source_404(
        self, client: AsyncClient, registered_source, db_session
    ):
        """Event exists but source doesn't match — returns 404."""
        from services.webhook.crud import create_webhook_source

        other_source = await create_webhook_source(
            session=db_session,
            name="other-source",
        )

        delivery_id = "cross-source-delivery"
        post_resp = await client.post(
            f"/api/v1/webhooks/{registered_source.name}",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers={
                "Content-Type": "application/json",
                "X-Delivery-Id": delivery_id,
            },
        )
        assert post_resp.status_code == 202

        get_resp = await client.get(
            f"/api/v1/webhooks/{other_source.name}/{delivery_id}"
        )
        assert get_resp.status_code == 404
