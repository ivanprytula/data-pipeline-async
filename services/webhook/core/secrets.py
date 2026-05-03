"""Secrets client for the webhook service.

Hierarchy (highest priority first):
1. Environment variable ``WEBHOOK_SIGNING_KEY_{SOURCE.upper()}``  (local dev / CI)
2. AWS Secrets Manager ``data-zoo/webhook/{source}/signing-key``   (production)
3. ``WEBHOOK_SIGNING_KEY_DEFAULT`` env var fallback                (dev catch-all)

The client caches resolved keys in memory with a 5-minute TTL to avoid
hammering Secrets Manager on every request. Cache is invalidated automatically
when the TTL expires so key rotations propagate within the TTL window.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)

# Cache TTL — resolved keys are re-fetched after this many seconds
_CACHE_TTL_SECONDS: int = 300  # 5 minutes


@dataclass
class _CacheEntry:
    value: str
    expires_at: float


@dataclass
class _SecretsCache:
    _store: dict[str, _CacheEntry] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry and time.monotonic() < entry.expires_at:
            return entry.value
        return None

    def set(self, key: str, value: str) -> None:
        self._store[key] = _CacheEntry(
            value=value, expires_at=time.monotonic() + _CACHE_TTL_SECONDS
        )

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)


_cache = _SecretsCache()


async def get_signing_key(source: str) -> str | None:
    """Resolve the HMAC signing key for a webhook source.

    Resolution order:
    1. In-memory cache (5-min TTL)
    2. Environment variable: ``WEBHOOK_SIGNING_KEY_{SOURCE_UPPER}``
    3. AWS Secrets Manager (if boto3 available and AWS_DEFAULT_REGION set)
    4. ``WEBHOOK_SIGNING_KEY_DEFAULT`` env var (dev fallback)

    Args:
        source: Webhook source name (e.g., ``'stripe'``, ``'segment'``).

    Returns:
        Signing key string, or ``None`` if no key is configured for this source.
    """
    cache_key = f"signing_key:{source}"

    # 1. Cache hit
    cached = _cache.get(cache_key)
    if cached:
        return cached

    # 2. Environment variable override (local dev, CI)
    env_key = os.environ.get(f"WEBHOOK_SIGNING_KEY_{source.upper().replace('-', '_')}")
    if env_key:
        _cache.set(cache_key, env_key)
        return env_key

    # 3. AWS Secrets Manager
    secret_name = f"data-zoo/webhook/{source}/signing-key"
    key = await _fetch_from_secrets_manager(secret_name)
    if key:
        _cache.set(cache_key, key)
        return key

    # 4. Default fallback (dev only — should not be used in production)
    default_key = os.environ.get("WEBHOOK_SIGNING_KEY_DEFAULT")
    if default_key:
        logger.warning(
            "webhook_signing_key_fallback",
            extra={"source": source, "reason": "using WEBHOOK_SIGNING_KEY_DEFAULT"},
        )
        _cache.set(cache_key, default_key)
        return default_key

    return None


async def _fetch_from_secrets_manager(secret_name: str) -> str | None:
    """Fetch a secret value from AWS Secrets Manager.

    Returns ``None`` if boto3 is unavailable, AWS credentials are not
    configured, or the secret does not exist. All errors are logged as
    warnings and suppressed so the caller can fall through to the next
    resolution step.

    Args:
        secret_name: Full Secrets Manager secret name.
    """
    try:
        import json

        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_name)
        raw = response.get("SecretString", "")
        parsed = json.loads(raw)
        return parsed.get("key") or parsed.get("value") or raw
    except ImportError:
        return None  # boto3 not installed (local dev without AWS SDK)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in ("ResourceNotFoundException", "AccessDeniedException"):
            logger.warning(
                "secrets_manager_fetch_failed",
                extra={"secret": secret_name, "error": str(exc)},
            )
        return None
    except Exception as exc:
        logger.warning(
            "secrets_manager_fetch_failed",
            extra={"secret": secret_name, "error": str(exc)},
        )
        return None
