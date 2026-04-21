"""External API fetching with retry logic and exponential backoff.

Uses real httpx.AsyncClient to fetch from jsonplaceholder.typicode.com.
Demonstrates resilience patterns: graceful failure, exponential backoff,
timeout handling, and clear error propagation.

Week 4 Phase 2 pattern: Real async HTTP with concurrency control.
"""

import asyncio
import contextlib
import logging

import httpx


logger = logging.getLogger(__name__)

# jsonplaceholder base URL (free, no authentication required)
EXTERNAL_API_BASE = "https://jsonplaceholder.typicode.com"

"""
Per-event-loop HTTP client management.

httpx.AsyncClient instances are bound to the event loop they were created on.
Sharing a single client across different asyncio event loops can cause
``RuntimeError: Event loop is closed`` when tests/consumers close a loop while a
client from another loop still exists. To avoid this, we keep a mapping of
running event loop -> AsyncClient and return the client for the current loop.

`get_http_client()` and `close_http_client()` operate on the current running
loop only, which is safe for tests that create/close loops per test. This is a
best-effort approach for cleanup; a `close_all_http_clients()` helper is also
provided for global shutdown if needed.
"""

# Mapping: event loop -> AsyncClient
_http_clients: dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}


async def get_http_client() -> httpx.AsyncClient:
    """Return an AsyncClient associated with the current running event loop.

    Ensures we don't reuse a client created on another event loop which would
    make closing it from the current loop raise ``RuntimeError: Event loop is
    closed``.
    """
    loop = asyncio.get_running_loop()
    client = _http_clients.get(loop)
    if client is not None:
        return client

    client = httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    _http_clients[loop] = client
    return client


async def close_http_client() -> None:
    """Close the AsyncClient associated with the current running event loop.

    Safe to call multiple times. If there's no running loop (e.g. being called
    from synchronous shutdown), this is a no-op.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop on this thread; nothing to close here.
        return

    client = _http_clients.pop(loop, None)
    if client is None:
        return

    with contextlib.suppress(RuntimeError):
        await client.aclose()


async def close_all_http_clients() -> None:
    """Best-effort close of all tracked AsyncClient instances.

    Iterates over the loop->client mapping and attempts to close each client.
    If the client's loop is different from the current running loop, this will
    schedule the coroutine on that loop using ``asyncio.run_coroutine_threadsafe``
    and wait briefly for completion. Any errors during close are swallowed to
    keep shutdown best-effort.
    """
    # Snapshot keys to avoid mutation during iteration
    loops = list(_http_clients.keys())
    for loop in loops:
        client = _http_clients.pop(loop, None)
        if client is None:
            continue
        try:
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop is loop:
                # Close directly on the same loop
                with contextlib.suppress(Exception):
                    await client.aclose()
            elif loop.is_running():
                # Close on the client's loop thread-safely
                try:
                    fut = asyncio.run_coroutine_threadsafe(client.aclose(), loop)
                    # wait a short time for the close to complete
                    fut.result(timeout=1)
                except Exception as e:
                    logger.debug("http_client_cleanup_error", extra={"error": str(e)})
            else:
                # Loop not running; close client directly to avoid resource warning
                try:
                    with contextlib.suppress(Exception):
                        await client.aclose()
                except RuntimeError:
                    # If we can't close it, at least try to prevent resource leak
                    logger.debug("http_client_loop_stopped", extra={"loop": loop})
        except Exception:
            # Swallow any error to ensure best-effort cleanup
            pass


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
