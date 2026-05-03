"""Webhook API key generation, verification, and revocation.

API keys provide an additional authentication layer on top of HMAC signature
validation. Sources can optionally require an API key via the X-API-Key header.

Security (OWASP A02):
- Plaintext key is returned ONCE at creation and never stored.
- Only an Argon2id hash is persisted in the database.
- Key prefix (first 8 chars) is stored for display purposes only.

Key format:  wk_<32 random hex chars>
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.webhook.models import WebhookApiKey


logger = logging.getLogger(__name__)

# Argon2id with OWASP recommended parameters (time_cost=3, memory_cost=65536)
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

_KEY_PREFIX = "wk_"
_KEY_RAW_LENGTH = 32  # bytes → 64 hex chars


def _generate_raw_key() -> str:
    """Generate a cryptographically random API key.

    Returns:
        Raw API key string in format ``wk_<64 hex chars>``.
    """
    return _KEY_PREFIX + secrets.token_hex(_KEY_RAW_LENGTH)


async def create_api_key(
    db: AsyncSession,
    source_id: int,
    label: str | None = None,
) -> tuple[WebhookApiKey, str]:
    """Create a new API key for a webhook source.

    The plaintext key is returned ONCE. Only the Argon2id hash is stored.

    Args:
        db: Active async database session.
        source_id: ID of the WebhookSource this key belongs to.
        label: Optional human-readable label (e.g., "production").

    Returns:
        Tuple of (WebhookApiKey ORM instance, plaintext_key). The plaintext_key
        must be returned to the caller and will not be recoverable afterwards.
    """
    raw_key = _generate_raw_key()
    key_hash = _hasher.hash(raw_key)
    key_prefix = raw_key[: len(_KEY_PREFIX) + 8]  # "wk_" + first 8 hex chars

    api_key = WebhookApiKey(
        source_id=source_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        label=label,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info(
        "api_key_created",
        extra={"source_id": source_id, "key_id": api_key.id, "prefix": key_prefix},
    )
    return api_key, raw_key


async def revoke_api_key(
    db: AsyncSession,
    source_id: int,
    key_id: int,
) -> WebhookApiKey | None:
    """Revoke an API key by marking it inactive.

    Args:
        db: Active async database session.
        source_id: ID of the owning WebhookSource (for ownership check).
        key_id: ID of the WebhookApiKey to revoke.

    Returns:
        Updated WebhookApiKey instance, or None if not found / wrong source.
    """
    result = await db.execute(
        select(WebhookApiKey).where(
            WebhookApiKey.id == key_id,
            WebhookApiKey.source_id == source_id,
            WebhookApiKey.is_active.is_(True),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None

    api_key.is_active = False
    api_key.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(api_key)

    logger.info(
        "api_key_revoked",
        extra={"source_id": source_id, "key_id": key_id},
    )
    return api_key


async def verify_api_key(
    db: AsyncSession,
    source_id: int,
    raw_key: str,
) -> bool:
    """Verify a raw API key against stored Argon2id hashes for a source.

    Updates last_used_at on the matching key record.

    Args:
        db: Active async database session.
        source_id: ID of the WebhookSource.
        raw_key: Plaintext API key from the X-API-Key header.

    Returns:
        True if a valid active key matches, False otherwise.
    """
    if not raw_key.startswith(_KEY_PREFIX):
        return False

    result = await db.execute(
        select(WebhookApiKey).where(
            WebhookApiKey.source_id == source_id,
            WebhookApiKey.is_active.is_(True),
        )
    )
    active_keys = result.scalars().all()

    for key_record in active_keys:
        try:
            _hasher.verify(key_record.key_hash, raw_key)
            # Update last_used_at on match
            key_record.last_used_at = datetime.now(UTC).replace(tzinfo=None)
            await db.commit()
            return True
        except VerifyMismatchError:
            continue

    return False


async def list_api_keys(
    db: AsyncSession,
    source_id: int,
) -> list[WebhookApiKey]:
    """List all API keys for a source (active and revoked).

    Args:
        db: Active async database session.
        source_id: ID of the WebhookSource.

    Returns:
        List of WebhookApiKey instances (key_hash is NOT included in responses).
    """
    result = await db.execute(
        select(WebhookApiKey)
        .where(WebhookApiKey.source_id == source_id)
        .order_by(WebhookApiKey.created_at.desc())
    )
    return list(result.scalars().all())
