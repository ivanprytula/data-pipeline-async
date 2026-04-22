"""Retry and backoff policies for resilient ingestion.

Provides:
- Exponential backoff decorator with jitter
- Idempotency key tracking (for deduplication)
- Safe cancellation handling
- Structured failure reporting

Design principles:
- Backoff is applied between attempts, not concurrent
- Idempotency must be enforced by the caller (via unique constraints or explicit checks)
- Cancellation is always preserved (CancelledError re-raised)
- Failures are logged with context for debugging
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from ingestor.rate_limiting_advanced import apply_jitter


logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> Callable[[F], F]:
    """Decorator for exponential backoff with optional jitter on async functions.

    Usage:
        @exponential_backoff(max_retries=3, base_delay=1.0)
        async def ingest_records(records: list[RecordRequest], db: AsyncSession) -> int:
            return await crud.create_records_batch(db, records)

    Args:
        max_retries: Number of retries (total attempts = max_retries + 1).
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay between attempts (caps exponential growth).
        jitter: If True, add ±20% variance to delay via apply_jitter (prevents thundering herd).

    Raises:
        Exception: The last exception after all retries exhausted.
        asyncio.CancelledError: Always re-raised (cancellation is never suppressed).

    Notes:
        - Delay formula: min(base_delay * (2 ** attempt), max_delay) + jitter
        - Jitter is ±20% of the calculated delay (via apply_jitter())
        - Suitable for transient failures (network, database locks, timeouts)
        - NOT suitable for non-idempotent operations (e.g., creating without unique constraint)
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except asyncio.CancelledError:
                    # Always preserve cancellation
                    raise
                except Exception as e:
                    last_exception = e

                    if attempt < max_retries:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (2**attempt), max_delay)

                        # Apply jitter (±20%) if enabled to prevent thundering herd
                        if jitter:
                            jitter_amount = delay * 0.2
                            delay = apply_jitter(delay, -jitter_amount, jitter_amount)

                        logger.warning(
                            "retry_attempt",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries + 1,
                                "delay_seconds": delay,
                                "error": str(e),
                            },
                        )

                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "retry_exhausted",
                            extra={
                                "function": func.__name__,
                                "total_attempts": max_retries + 1,
                                "error": str(last_exception),
                            },
                        )

            # Raise the last exception after all retries exhausted
            assert last_exception is not None, "Exception must be set after retry loop"
            raise last_exception

        return wrapper  # type: ignore

    return decorator


class IdempotencyKeyTracker:
    """Simple in-memory tracker for deduplication (for testing and single-instance deployments).

    For distributed systems, use a database or Redis-backed approach.

    Usage:
        tracker = IdempotencyKeyTracker()

        async def process_message(msg_id: str, data: dict) -> None:
            if tracker.is_duplicate(msg_id):
                logger.info("duplicate_skipped", extra={"key": msg_id})
                return
            # Process message...
            tracker.mark_seen(msg_id)
    """

    def __init__(self, ttl_seconds: int = 3600):
        """Initialize tracker.

        Args:
            ttl_seconds: Time-to-live for tracked keys (simple time-based cleanup).
        """
        self._seen: dict[str, float] = {}
        self.ttl_seconds = ttl_seconds

    def is_duplicate(self, key: str) -> bool:
        """Check if key has been seen before (and is not expired).

        Args:
            key: Idempotency key or message ID.

        Returns:
            True if key was previously marked as seen and not yet expired.
        """
        import time

        if key not in self._seen:
            return False

        # Check TTL
        age = time.time() - self._seen[key]
        if age > self.ttl_seconds:
            del self._seen[key]
            return False

        return True

    def mark_seen(self, key: str) -> None:
        """Mark a key as processed.

        Args:
            key: Idempotency key or message ID.
        """
        import time

        self._seen[key] = time.time()

    def cleanup_expired(self) -> None:
        """Remove expired entries (call periodically if tracker is long-lived)."""
        import time

        current_time = time.time()
        expired = [
            k for k, v in self._seen.items() if current_time - v > self.ttl_seconds
        ]
        for k in expired:
            del self._seen[k]
