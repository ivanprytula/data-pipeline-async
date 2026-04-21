"""External API fetching with aiohttp and retry logic.

Uses real aiohttp.ClientSession to fetch from restcountries.com (country data).
Demonstrates aiohttp-specific patterns: session lifecycle, timeout config,
connector pooling, and error handling.

Week 4 Phase 2 alternative pattern: aiohttp for multi-tool exposure.
"""

import asyncio
import logging

import aiohttp


logger = logging.getLogger(__name__)

# REST Countries API base URL (free, no authentication required)
EXTERNAL_API_BASE = "https://restcountries.com/v3.1"

# Global aiohttp session (reused across calls for connection pooling)
_http_session: aiohttp.ClientSession | None = None


async def get_http_session() -> aiohttp.ClientSession:
    """Get or create global aiohttp ClientSession.

    Connection pooling improves performance for multiple requests.
    Uses TCPConnector with configurable pool size.

    Returns:
        ClientSession configured with timeout and connector pool.
    """
    global _http_session
    if _http_session is None:
        # aiohttp-specific timeout configuration (total, connect, sock_read)
        timeout = aiohttp.ClientTimeout(
            total=30.0,  # Total request timeout
            connect=10.0,  # Connection establishment timeout
            sock_read=10.0,  # Socket read timeout
        )
        # Connection pooling via TCPConnector
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connections
            limit_per_host=20,  # Connections per host
            ttl_dns_cache=300,  # DNS cache TTL in seconds
        )
        _http_session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
        )
    return _http_session


async def close_http_session() -> None:
    """Close the global aiohttp session (call on app shutdown)."""
    global _http_session
    if _http_session is not None:
        await _http_session.close()
        _http_session = None


async def fetch_from_external_api(
    resource: str,
    simulate_failures: bool = False,
) -> dict | list:
    """Fetch from external API (REST Countries).

    Args:
        resource: API resource path (e.g., 'name/United States').
                 Full URL: https://restcountries.com/v3.1/{resource}
        simulate_failures: If True, randomly fail 10% of requests (for testing).

    Returns:
        dict or list: Parsed JSON response.

    Raises:
        aiohttp.ClientError: If request fails (timeout, connection, etc).
        asyncio.TimeoutError: If request exceeds timeout.
        Exception: If simulate_failures=True and random failure triggered.
    """
    # For testing: simulate 10% random failures
    if simulate_failures:
        import random

        if random.random() < 0.1:
            raise Exception("Simulated API failure (testing)")

    url = f"{EXTERNAL_API_BASE}/{resource}"
    session = await get_http_session()

    try:
        async with session.get(url) as response:
            response.raise_for_status()  # Raise on 4xx/5xx
            return await response.json()
    except TimeoutError:
        logger.error("fetch_timeout", extra={"url": url, "error": "Request timeout"})
        raise
    except aiohttp.ClientError as e:
        logger.error(
            "fetch_http_error",
            extra={
                "url": url,
                "status": getattr(e, "status", None),
                "error": str(e),
            },
        )
        raise


async def fetch_with_retry(
    resource: str,
    max_retries: int = 3,
    simulate_failures: bool = False,
) -> dict | list:
    """Fetch from external API with exponential backoff retry.

    Pattern: Try up to `max_retries` times, waiting 2^attempt seconds between.
    - Attempt 1: immediate
    - Attempt 2: wait 1s, then try
    - Attempt 3: wait 2s, then try
    - Attempt 4: wait 4s, then try
    - If all fail, raise the last exception.

    Args:
        resource: API resource path (e.g., 'name/United States').
        max_retries: Number of retry attempts (default: 3).
        simulate_failures: If True, use simulated 10% failure rate (for testing).

    Returns:
        dict or list: Response from external API.

    Raises:
        aiohttp.ClientError or asyncio.TimeoutError if all retries exhausted.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            logger.info(
                "fetch_attempt",
                extra={
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "resource": resource,
                },
            )
            result = await fetch_from_external_api(
                resource, simulate_failures=simulate_failures
            )
            logger.info(
                "fetch_success",
                extra={
                    "attempt": attempt + 1,
                    "resource": resource,
                    "retries_used": attempt,
                },
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
                        "resource": resource,
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
                        "resource": resource,
                        "error": str(e),
                    },
                )

    # All retries exhausted
    if last_exception is not None:
        raise last_exception
    else:
        raise Exception("Unknown error occurred during fetch")
