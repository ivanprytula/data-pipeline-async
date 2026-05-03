"""Tests for webhook API key lifecycle (Phase 13.3)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.webhook.models import WebhookSource
from services.webhook.services.api_keys import (
    create_api_key,
    list_api_keys,
    revoke_api_key,
    verify_api_key,
)
from services.webhook.services.replay_daemon import compute_next_retry_at
from services.webhook.services.signature import (
    _compute_hmac,
    validate_signature_versioned,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_session():
    """In-memory SQLite async session with webhook schema."""
    from sqlalchemy.ext.asyncio import (
        async_sessionmaker,
        create_async_engine,
    )

    from services.webhook.models import Base  # type: ignore[attr-defined]

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def webhook_source(db_session: AsyncSession) -> WebhookSource:
    """Create a WebhookSource row for testing."""
    source = WebhookSource(
        name="test_source",
        description="Test",
        signing_key_secret_name="test/key",
        signing_algorithm="hmac-sha256",
        rate_limit_per_minute=100,
        is_active=True,
        signing_key_version=1,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


# ── API key generation ────────────────────────────────────────────────────────


async def test_create_api_key_returns_model_and_plaintext(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    api_key, plaintext = await create_api_key(db_session, webhook_source.id)
    assert api_key.id is not None
    assert plaintext.startswith("wk_")
    assert len(plaintext) > 10
    # Hash must differ from plaintext
    assert api_key.key_hash != plaintext


async def test_create_api_key_stores_prefix(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    api_key, plaintext = await create_api_key(db_session, webhook_source.id)
    # key_prefix = first 8 chars of "wk_..." plus separator
    assert plaintext.startswith(api_key.key_prefix.replace("...", ""))


async def test_create_api_key_is_active(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    api_key, _ = await create_api_key(db_session, webhook_source.id)
    assert api_key.is_active is True
    assert api_key.revoked_at is None


# ── API key verification ──────────────────────────────────────────────────────


async def test_verify_api_key_succeeds_with_correct_key(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    _, plaintext = await create_api_key(db_session, webhook_source.id)
    assert await verify_api_key(db_session, webhook_source.id, plaintext) is True


async def test_verify_api_key_fails_with_wrong_key(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    await create_api_key(db_session, webhook_source.id)
    assert await verify_api_key(db_session, webhook_source.id, "wk_wrong_key") is False


async def test_verify_api_key_fails_for_different_source(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    _, plaintext = await create_api_key(db_session, webhook_source.id)
    assert await verify_api_key(db_session, webhook_source.id + 99, plaintext) is False


# ── Revocation ────────────────────────────────────────────────────────────────


async def test_revoke_api_key_marks_inactive(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    api_key, _ = await create_api_key(db_session, webhook_source.id)
    revoked = await revoke_api_key(db_session, webhook_source.id, api_key.id)
    assert revoked is not None
    assert revoked.is_active is False
    assert revoked.revoked_at is not None


async def test_revoked_key_fails_verification(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    api_key, plaintext = await create_api_key(db_session, webhook_source.id)
    await revoke_api_key(db_session, webhook_source.id, api_key.id)
    assert await verify_api_key(db_session, webhook_source.id, plaintext) is False


async def test_revoke_nonexistent_key_returns_none(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    result = await revoke_api_key(db_session, webhook_source.id, 999_999)
    assert result is None


# ── List keys ─────────────────────────────────────────────────────────────────


async def test_list_api_keys_returns_all_keys_for_source(
    db_session: AsyncSession, webhook_source: WebhookSource
) -> None:
    await create_api_key(db_session, webhook_source.id, label="first")
    await create_api_key(db_session, webhook_source.id, label="second")
    keys = await list_api_keys(db_session, webhook_source.id)
    assert len(keys) == 2


# ── Retry backoff schedule ───────────────────────────────────────────────────


_DEFAULT_CONFIG = {
    "max_attempts": 5,
    "backoff_base_seconds": 30,
    "backoff_multiplier": 2,
}


def test_compute_next_retry_at_first_attempt() -> None:
    dt = compute_next_retry_at(0, _DEFAULT_CONFIG)
    assert dt is not None
    from datetime import UTC, datetime

    delta = (dt - datetime.now(UTC).replace(tzinfo=None)).total_seconds()
    assert 28 < delta < 35  # ~30 seconds


def test_compute_next_retry_at_doubles_each_time() -> None:
    delays = []
    for attempt in range(4):
        dt = compute_next_retry_at(attempt, _DEFAULT_CONFIG)
        assert dt is not None
        from datetime import UTC, datetime

        delays.append((dt - datetime.now(UTC).replace(tzinfo=None)).total_seconds())

    # Each delay should be roughly double the previous
    for i in range(1, len(delays)):
        assert delays[i] > delays[i - 1] * 1.5  # allow timing jitter


def test_compute_next_retry_at_returns_none_at_max_attempts() -> None:
    # max_attempts=5 means attempts 0-4 are valid; attempt 5 exceeds limit
    assert compute_next_retry_at(5, _DEFAULT_CONFIG) is None


def test_compute_next_retry_at_returns_none_beyond_max() -> None:
    assert compute_next_retry_at(10, _DEFAULT_CONFIG) is None


# ── Signature key rotation grace period ─────────────────────────────────────


async def test_validate_signature_versioned_accepts_deprecated_key_within_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b'{"event":"ok"}'
    source = "stripe"
    deprecated_key = "deprecated-secret"
    header_signature = _compute_hmac(body, deprecated_key)

    async def fake_get_signing_key(name: str) -> str | None:
        if name == source:
            return "current-secret"
        if name == f"{source}/v1":
            return deprecated_key
        return None

    monkeypatch.setattr(
        "services.webhook.services.signature.get_signing_key",
        fake_get_signing_key,
    )

    import time

    is_valid, matched_version = await validate_signature_versioned(
        body=body,
        header_signature=header_signature,
        source=source,
        current_version=2,
        deprecated_version=1,
        deprecated_at=time.time() - 3600,
        grace_period_days=7,
    )

    assert is_valid is True
    assert matched_version == 1


async def test_validate_signature_versioned_rejects_deprecated_key_after_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b'{"event":"expired"}'
    source = "stripe"
    deprecated_key = "deprecated-secret"
    header_signature = _compute_hmac(body, deprecated_key)

    async def fake_get_signing_key(name: str) -> str | None:
        if name == source:
            return "current-secret"
        if name == f"{source}/v1":
            return deprecated_key
        return None

    monkeypatch.setattr(
        "services.webhook.services.signature.get_signing_key",
        fake_get_signing_key,
    )

    import time

    is_valid, matched_version = await validate_signature_versioned(
        body=body,
        header_signature=header_signature,
        source=source,
        current_version=2,
        deprecated_version=1,
        deprecated_at=time.time() - (8 * 86400),
        grace_period_days=7,
    )

    assert is_valid is False
    assert matched_version is None
