"""Unit tests for HMAC-SHA256 signature validation."""

from __future__ import annotations

import hashlib
import hmac as hmac_lib
import os
from unittest.mock import patch

import pytest

from services.webhook.core import secrets as secrets_module
from services.webhook.services.signature import (
    _compute_hmac,
    _extract_signature_value,
    validate_signature,
)


@pytest.fixture(autouse=True)
def clear_secrets_cache():
    """Reset the in-memory secrets cache before each test.

    Prevents cached signing keys from leaking between tests that use
    different keys for the same source (e.g., multiple 'stripe' tests).
    """
    secrets_module._cache._store.clear()
    yield
    secrets_module._cache._store.clear()


class TestComputeHmac:
    """Tests for the HMAC computation helper."""

    def test_produces_hex_digest(self):
        digest = _compute_hmac(b"hello world", "secret")
        assert len(digest) == 64  # sha256 hex is 64 chars
        assert all(c in "0123456789abcdef" for c in digest)

    def test_consistent_output(self):
        """Same body + key always produces same digest."""
        a = _compute_hmac(b"payload", "key")
        b = _compute_hmac(b"payload", "key")
        assert a == b

    def test_different_key_different_digest(self):
        a = _compute_hmac(b"payload", "key-a")
        b = _compute_hmac(b"payload", "key-b")
        assert a != b

    def test_matches_stdlib_hmac(self):
        body = b"test body"
        key = "my-secret"
        expected = hmac_lib.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert _compute_hmac(body, key) == expected


class TestExtractSignatureValue:
    """Tests for header normalisation."""

    def test_plain_hex_passthrough(self):
        sig = "abcdef1234567890" * 4
        assert _extract_signature_value(sig) == sig

    def test_stripe_format_extracts_v1(self):
        hex_sig = "a" * 64
        header = f"t=1614556800,v1={hex_sig}"
        assert _extract_signature_value(header) == hex_sig

    def test_whitespace_stripped(self):
        sig = "  abcdef  "
        assert _extract_signature_value(sig) == "abcdef"


class TestValidateSignature:
    """Tests for the high-level validate_signature coroutine."""

    async def test_valid_signature_returns_true(self):
        key = "super-secret"
        body = b'{"event":"test"}'
        correct_sig = _compute_hmac(body, key)

        with patch.dict(os.environ, {"WEBHOOK_SIGNING_KEY_STRIPE": key}):
            result = await validate_signature(
                body=body,
                header_signature=correct_sig,
                source="stripe",
            )
        assert result is True

    async def test_wrong_signature_returns_false(self):
        key = "super-secret"
        body = b'{"event":"test"}'

        with patch.dict(os.environ, {"WEBHOOK_SIGNING_KEY_STRIPE": key}):
            result = await validate_signature(
                body=body,
                header_signature="badhash" + "0" * 57,
                source="stripe",
            )
        assert result is False

    async def test_empty_header_returns_false(self):
        """Missing signature header → returns False (not an error)."""
        result = await validate_signature(
            body=b"body",
            header_signature="",
            source="stripe",
        )
        assert result is False

    async def test_no_key_configured_returns_false(self):
        """No signing key configured for source → returns False."""
        env_without_key = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("WEBHOOK_SIGNING_KEY")
        }
        with patch.dict(os.environ, env_without_key, clear=True):
            result = await validate_signature(
                body=b"body",
                header_signature="somesig",
                source="unknown-source",
            )
        assert result is False

    async def test_stripe_format_signature(self):
        """Stripe-style 't=<ts>,v1=<sig>' header is correctly parsed."""
        key = "stripe-key"
        body = b'{"type":"charge.succeeded"}'
        correct_sig = _compute_hmac(body, key)
        stripe_header = f"t=1614556800,v1={correct_sig}"

        with patch.dict(os.environ, {"WEBHOOK_SIGNING_KEY_STRIPE": key}):
            result = await validate_signature(
                body=body,
                header_signature=stripe_header,
                source="stripe",
            )
        assert result is True
