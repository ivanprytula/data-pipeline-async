"""Scraper router — POST /api/v1/scrape/{source}.

Flow: scrape → MongoDB → Kafka event (fail-open on both)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from ingestor import events
from ingestor.constants import API_V1_PREFIX
from ingestor.schemas import ScrapeResponse
from ingestor.scrapers import ScraperFactory
from ingestor.storage import mongo


logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{API_V1_PREFIX}/scrape", tags=["scraper"])


@router.post(
    "/{source}",
    response_model=ScrapeResponse,
    status_code=status.HTTP_200_OK,
    summary="Scrape a source and store results in MongoDB",
    description=(
        "Trigger a scrape for the given source and persist results to MongoDB.\n\n"
        "**Available sources:**\n"
        "- `jsonplaceholder` — httpx REST API (JSONPlaceholder)\n"
        "- `hn` — BeautifulSoup HTML (Hacker News front page)\n"
        "- `playwright` — headless Chromium JS-rendered page (requires `playwright install chromium`)\n\n"  # noqa: E501
        "A Kafka event `doc.scraped` is published after storage (fail-open)."
    ),
)
async def scrape_source(source: str, limit: int = 20) -> ScrapeResponse:
    """Scrape `source`, persist to MongoDB, publish Kafka event.

    Args:
        source: Registered scraper name (e.g., 'hn', 'jsonplaceholder', 'playwright').
        limit: Maximum number of items to scrape (1–100).

    Returns:
        ScrapeResponse with counts of scraped and stored items.
    """
    limit = max(1, min(limit, 100))

    try:
        scraper = ScraperFactory.create(source)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    items = await scraper.scrape(limit=limit)
    logger.info("scrape_complete", extra={"source": source, "count": len(items)})

    stored = 0
    for item in items:
        try:
            await mongo.insert_scraped_doc(
                source=item.source,
                url=item.url,
                title=item.title,
                content=item.content,
            )
            stored += 1
        except Exception as exc:
            logger.warning(
                "mongo_insert_failed",
                extra={"source": source, "url": item.url, "error": str(exc)},
            )

    await events.publish_doc_scraped(source=source, count=stored)

    return ScrapeResponse(source=source, scraped=len(items), stored=stored)
