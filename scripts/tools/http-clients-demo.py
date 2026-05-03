"""
Demo: Side-by-Side httpx vs aiohttp Usage

Run with: uv run python scripts/tools/http-clients-demo.py
(or add to your startup for visual comparison)
"""

import asyncio
import logging
import sys
from pathlib import Path


# Add parent directory to path so 'app' can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging to see the retry patterns
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def demo_httpx():
    """Demo: httpx for fetching blog posts (jsonplaceholder)."""
    logger.info("=" * 70)
    logger.info("HTTPX DEMO: Fetching blog posts from jsonplaceholder.typicode.com")
    logger.info("=" * 70)

    from services.ingestor.fetch import close_http_client, fetch_with_retry

    try:
        # Fetch a blog post
        result = await fetch_with_retry(
            "https://jsonplaceholder.typicode.com/posts/1",
            max_retries=2,
        )
        logger.info(f"✅ HTTPX Success: Fetched post '{result['title']}'")
        logger.info(f"   Body excerpt: {result['body'][:80]}...")

        # Fetch another concurrently to show connection reuse
        result2 = await fetch_with_retry(
            "https://jsonplaceholder.typicode.com/posts/2",
            max_retries=2,
        )
        logger.info(f"✅ HTTPX Success: Fetched post '{result2['title']}'")

    except Exception as e:
        logger.error(f"❌ HTTPX Error: {e}", exc_info=True)
    finally:
        await close_http_client()
        logger.info("HTTPX client closed ✓\n")


async def demo_aiohttp():
    """Demo: aiohttp for fetching country data (REST Countries)."""
    logger.info("=" * 70)
    logger.info("AIOHTTP DEMO: Fetching country data from restcountries.com")
    logger.info("=" * 70)

    from services.ingestor.fetch_aiohttp import close_http_session, fetch_with_retry

    try:
        # Fetch country data
        result = await fetch_with_retry(
            "name/United%20States",  # REST Countries resource format
            max_retries=2,
        )
        # Result is a list when searching by name, take first match
        if isinstance(result, list) and result:
            country = result[0]
            logger.info(
                f"✅ AIOHTTP Success: Fetched country '{country['name']['common']}'"
            )
            logger.info(f"   Capital: {country.get('capital', ['N/A'])[0]}")
            logger.info(f"   Region: {country.get('region', 'N/A')}")

        # Fetch another country to show connection reuse
        result2 = await fetch_with_retry(
            "name/Germany",
            max_retries=2,
        )
        if isinstance(result2, list) and result2:
            country2 = result2[0]
            logger.info(
                f"✅ AIOHTTP Success: Fetched country '{country2['name']['common']}'"
            )

    except Exception as e:
        logger.error(f"❌ AIOHTTP Error: {e}", exc_info=True)
    finally:
        await close_http_session()
        logger.info("AIOHTTP session closed ✓\n")


async def demo_concurrent_requests():
    """Demo: Concurrent requests with both clients."""
    logger.info("=" * 70)
    logger.info("CONCURRENT DEMO: Multiple requests in parallel")
    logger.info("=" * 70)

    from services.ingestor.fetch import close_http_client
    from services.ingestor.fetch import fetch_with_retry as httpx_fetch
    from services.ingestor.fetch_aiohttp import (
        close_http_session,
    )
    from services.ingestor.fetch_aiohttp import (
        fetch_with_retry as aiohttp_fetch,
    )

    try:
        # Fire off multiple requests concurrently
        logger.info("Fetching 3 blog posts with httpx...")
        httpx_tasks = [
            httpx_fetch(
                f"https://jsonplaceholder.typicode.com/posts/{i}", max_retries=1
            )
            for i in range(1, 4)
        ]
        httpx_results = await asyncio.gather(*httpx_tasks)
        logger.info(f"✅ Got {len(httpx_results)} posts with httpx")

        logger.info("Fetching 3 countries with aiohttp...")
        countries = ["France", "Spain", "Italy"]
        aiohttp_tasks = [
            aiohttp_fetch(f"name/{country}", max_retries=1) for country in countries
        ]
        aiohttp_results = await asyncio.gather(*aiohttp_tasks)
        logger.info(f"✅ Got {len(aiohttp_results)} countries with aiohttp")

    except Exception as e:
        logger.error(f"❌ Concurrent Error: {e}", exc_info=True)
    finally:
        await close_http_client()
        await close_http_session()
        logger.info("All clients closed ✓\n")


async def demo_comparison():
    """Side-by-side comparison of API patterns."""
    logger.info("=" * 70)
    logger.info("API COMPARISON: httpx vs aiohttp")
    logger.info("=" * 70)

    print(
        """
HTTPX (requests-like):
  Client Type: AsyncClient
  Timeout: timeout=30.0 (simple)
  Pool: limits=Limits(max_connections=100)
  Request: await client.get(url)
  JSON: response.json()
  Close: await client.aclose()
  Exception: httpx.TimeoutException
  Use Case: Modern microservices, startups

AIOHTTP (aiohttp-native):
  Session Type: ClientSession
  Timeout: ClientTimeout(total=30, connect=10, sock_read=10) (granular)
  Pool: TCPConnector(limit=100, limit_per_host=20)
  Request: async with client.get(url) as r:
  JSON: await response.json()
  Close: await session.close()
  Exception: asyncio.TimeoutError
  Use Case: Enterprise systems, mature codebases

KEY DIFFERENCES:
  • httpx: Simpler API, HTTP/2 support
  • aiohttp: More control, enterprise battle-tested
  • httpx: Last update Dec 2024
  • aiohttp: Last update Mar 2026 (more recent)
  • httpx: Lighter memory footprint
  • aiohttp: More features, heavier footprint
"""
    )


async def main():
    """Run all demos."""
    logger.info("\n" + "=" * 70)
    logger.info("HTTP CLIENTS DEMO: httpx vs aiohttp")
    logger.info("=" * 70 + "\n")

    # Show comparison table
    await demo_comparison()

    # Run actual demos
    await demo_httpx()
    await demo_aiohttp()
    await demo_concurrent_requests()

    logger.info("=" * 70)
    logger.info("DEMO COMPLETE ✓")
    logger.info("=" * 70)
    logger.info("\nNext steps for your job search:")
    logger.info("1. Mention both clients in your resume/portfolio")
    logger.info("2. Reference the comparison doc: docs/httpx-vs-aiohttp-comparison.md")
    logger.info("3. In interviews, discuss trade-offs confidently")
    logger.info("4. Share this demo as proof of practical knowledge\n")


if __name__ == "__main__":
    """
    Run the demo:

    $ cd /home/$USER/<directory>/data-pipeline-async
    $ uv run python scripts/tools/http-clients-demo.py

    This requires the app to have working fetch modules and access to:
    - https://jsonplaceholder.typicode.com (httpx demo)
    - https://restcountries.com/v3.1 (aiohttp demo)
    """
    asyncio.run(main())
