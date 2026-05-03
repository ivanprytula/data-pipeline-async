"""HMAC-SHA256 webhook signature validation.

Each webhook source signs its payloads with a shared secret. The signature
is transmitted in the request header (typically ``X-Webhook-Signature`` or a
source-specific header like ``X-Stripe-Signature``). This module validates
the signature using constant-time comparison to prevent timing-based attacks.

Supported format::

    X-Webhook-Signature: <hex-encoded HMAC-SHA256 digest>

Stripe-extended format (payload prefixed with ``t=<timestamp>,v1=``)::

    X-Stripe-Signature: t=1614556800,v1=<hex-encoded HMAC-SHA256 digest>

Usage::

    is_valid = await validate_signature(
        body=raw_request_body,
        header_signature=request.headers.get("X-Webhook-Signature", ""),
        source="stripe",
    )
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from services.webhook.core.secrets import get_signing_key


logger = logging.getLogger(__name__)


def _compute_hmac(body: bytes, key: str) -> str:
    """Compute HMAC-SHA256 digest of *body* using *key*.

    Args:
        body: Raw request body bytes.
        key: Signing key string (UTF-8 encoded internally).

    Returns:
        Lowercase hex-encoded digest string.
    """
    return hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _extract_signature_value(raw_header: str) -> str:
    """Normalise the signature header value.

    Handles two formats:

    - Plain hex: ``abcdef1234...``
    - Stripe format: ``t=1614556800,v1=abcdef1234...``

    Args:
        raw_header: Raw value of the signature header.

    Returns:
        Hex digest string only (no prefix).
    """
    raw = raw_header.strip()
    # Stripe: "t=<ts>,v1=<sig>"
    for part in raw.split(","):
        part = part.strip()
        if part.startswith("v1="):
            return part[3:]
    # Generic: plain hex
    return raw


async def validate_signature(
    body: bytes,
    header_signature: str,
    source: str,
) -> bool:
    """Validate the HMAC-SHA256 signature for an inbound webhook.

    Uses ``hmac.compare_digest`` (constant-time) to prevent timing-based
    signature-forgery attacks.

    Args:
        body: Raw request body bytes. Must be the exact bytes received over
            the wire — not re-serialised JSON — to prevent whitespace attacks.
        header_signature: Value of the signature header from the request.
        source: Webhook source name used to look up the signing key.

    Returns:
        ``True`` if signature is valid, ``False`` otherwise (including when
        no key is configured or the header is missing/empty).
    """
    if not header_signature:
        logger.info(
            "webhook_signature_missing",
            extra={"source": source},
        )
        return False

    signing_key = await get_signing_key(source)
    if not signing_key:
        logger.warning(
            "webhook_signing_key_not_configured",
            extra={"source": source},
        )
        return False

    expected = _compute_hmac(body, signing_key)
    received = _extract_signature_value(header_signature)

    is_valid = hmac.compare_digest(expected, received)

    if not is_valid:
        logger.warning(
            "webhook_signature_mismatch",
            extra={"source": source},
        )

    return is_valid
