"""External API fetching with retry logic and exponential backoff.

Demonstrates resilience patterns: graceful failure, exponential backoff, and
clear error propagation. Week 2 Milestone 4 pattern.
"""

import asyncio
import logging
import random


logger = logging.getLogger(__name__)


async def fetch_from_external_api(url: str) -> dict:
    """Simulate calling an external API with occasional failures.

    10% failure rate (raises Exception).
    90% success rate (returns {"data": "success"}).

    Args:
        url: Simulated API endpoint (unused, for demonstration).

    Returns:
        dict with "data" field on success.

    Raises:
        Exception: If random() < 0.1 (simulated transient failure).
    """
    if random.random() < 0.1:
        raise Exception("API temporarily unavailable")
    return {"data": "success"}


async def fetch_with_retry(
    url: str,
    max_retries: int = 3,
) -> dict:
    """Fetch from external API with exponential backoff retry.

    Pattern: Try up to `max_retries` times, waiting 2^attempt seconds between.
    - Attempt 0: immediate
    - Attempt 1: wait 1s, then try
    - Attempt 2: wait 2s, then try
    - Attempt 3: wait 4s, then try
    - If all fail, raise the last exception.

    Args:
        url: API endpoint to fetch from.
        max_retries: Number of retry attempts (default: 3).

    Returns:
        dict: Response from external API.

    Raises:
        Exception: If all retries are exhausted.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            logger.info("fetch_attempt", extra={"attempt": attempt + 1, "url": url})
            result = await fetch_from_external_api(url)
            logger.info(
                "fetch_success",
                extra={"attempt": attempt + 1, "url": url, "retries_used": attempt},
            )
            return result
        except Exception as e:
            last_exception = e

            # If this wasn't the last attempt, wait before retrying
            if attempt < max_retries - 1:
                delay = 2**attempt  # 1s, 2s, 4s...
                logger.warning(
                    "fetch_retry",
                    extra={
                        "attempt": attempt + 1,
                        "url": url,
                        "delay_seconds": delay,
                        "error": str(e),
                    },
                )
                await asyncio.sleep(delay)
            else:
                # Last attempt failed
                logger.error(
                    "fetch_exhausted",
                    extra={"max_retries": max_retries, "url": url, "error": str(e)},
                )

    # All retries exhausted
    if last_exception is not None:
        raise last_exception
    else:
        raise Exception("Unknown error occurred")