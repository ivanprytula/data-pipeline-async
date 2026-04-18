"""External API fetching with retry logic and exponential backoff.

Uses real httpx.AsyncClient to fetch from jsonplaceholder.typicode.com.
Demonstrates resilience patterns: graceful failure, exponential backoff,
timeout handling, and clear error propagation.

Week 4 Phase 2 pattern: Real async HTTP with concurrency control.
"""

import asyncio
import logging

import httpx


logger = logging.getLogger(__name__)

# jsonplaceholder base URL (free, no authentication required)
EXTERNAL_API_BASE = "https://jsonplaceholder.typicode.com"

# Global HTTP client (reused across calls for connection pooling)
_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    """Get or create global async HTTP client.

    Connection pooling improves performance for multiple requests.

    Returns:
        AsyncClient configured with timeout and limits.
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,  # 30 second timeout per request
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )
    return _http_client


async def close_http_client() -> None:
    """Close the global HTTP client (call on app shutdown)."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


async def fetch_from_external_api(
    url: str,
    simulate_failures: bool = False,
) -> dict:
    """Fetch from external API (jsonplaceholder).

    Args:
        url: Full URL to fetch (e.g., https://jsonplaceholder.typicode.com/posts/1).
        simulate_failures: If True, randomly fail 10% of requests (for testing).

    Returns:
        dict: Parsed JSON response.

    Raises:
        httpx.HTTPError: If request fails (timeout, connection error, 4xx/5xx).
        Exception: If simulate_failures=True and random failure triggered.
    """
    # For testing: simulate 10% random failures
    if simulate_failures:
        import random

        if random.random() < 0.1:
            raise Exception("Simulated API failure (testing)")

    client = await get_http_client()
    try:
        response = await client.get(url)
        response.raise_for_status()  # Raise on 4xx/5xx
        return response.json()
    except httpx.TimeoutException:
        logger.error("fetch_timeout", extra={"url": url, "error": "Request timeout"})
        raise
    except httpx.HTTPError as e:
        # Only HTTPStatusError has .response; others don't
        status = None
        if isinstance(e, httpx.HTTPStatusError):
            status = e.response.status_code

        logger.error(
            "fetch_http_error",
            extra={
                "url": url,
                "status": status,
                "error": str(e),
            },
        )
        raise


async def fetch_with_retry(
    url: str,
    max_retries: int = 3,
    simulate_failures: bool = False,
) -> dict:
    """Fetch from external API with exponential backoff retry.

    Pattern: Try up to `max_retries` times, waiting 2^attempt seconds between.
    - Attempt 1: immediate
    - Attempt 2: wait 1s, then try
    - Attempt 3: wait 2s, then try
    - Attempt 4: wait 4s, then try
    - If all fail, raise the last exception.

    Args:
        url: API endpoint to fetch from.
        max_retries: Number of retry attempts (default: 3).
        simulate_failures: If True, use simulated 10% failure rate (for testing).

    Returns:
        dict: Response from external API.

    Raises:
        httpx.HTTPError or Exception if all retries exhausted.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            logger.info(
                "fetch_attempt",
                extra={"attempt": attempt + 1, "max_retries": max_retries, "url": url},
            )
            result = await fetch_from_external_api(
                url, simulate_failures=simulate_failures
            )
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
                    extra={
                        "max_retries": max_retries,
                        "url": url,
                        "error": str(e),
                    },
                )

    # All retries exhausted
    if last_exception is not None:
        raise last_exception
    else:
        raise Exception("Unknown error occurred during fetch")
