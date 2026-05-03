"""Async MongoDB storage layer — Motor client singleton.

Modeled on app/cache.py singleton pattern:
- Module-level _client/_db singletons
- connect_mongo() / disconnect_mongo() for lifespan wiring
- All operations are pure async, fail-open on MongoError

Circuit breaker (Phase 4) wraps insert_scraped_doc so repeated MongoDB
failures open the circuit and stop hammering the database.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from services.ingestor.core.circuit_breaker import circuit_breaker


_client: AsyncIOMotorClient[dict[str, Any]] | None = None
_db: AsyncIOMotorDatabase[dict[str, Any]] | None = None

logger = logging.getLogger(__name__)

COLLECTION_SCRAPED = "scraped"


async def connect_mongo(mongo_url: str, db_name: str = "datazoo") -> None:
    """Initialize Motor async client and verify connectivity.

    Args:
        mongo_url: MongoDB connection URL (e.g., mongodb://localhost:27017).
        db_name: Database name to use.

    Raises:
        Exception: If MongoDB is unreachable (propagated to caller for logging).
    """
    global _client, _db
    _client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5_000)
    _db = _client[db_name]
    await _db.command("ping")
    logger.info("mongo_connected", extra={"url": mongo_url, "db": db_name})


async def disconnect_mongo() -> None:
    """Close MongoDB connection."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
    logger.info("mongo_disconnected")


@circuit_breaker(failure_threshold=5, recovery_timeout=30)
async def _mongo_insert_one(doc: dict[str, Any]) -> str:
    """Execute the MongoDB insert_one call guarded by the circuit breaker.

    Separated from the public API so the 'not connected' guard runs outside
    the breaker (connection absence is not a downstream failure worth tracking).

    Args:
        doc: Document dict to insert into the scraped collection.

    Returns:
        Inserted document ID as a string.

    Raises:
        RuntimeError: If the MongoDB client is not connected.
    """
    if _db is None:
        raise RuntimeError("MongoDB client not connected — ensure mongo_enabled=True")
    result = await _db[COLLECTION_SCRAPED].insert_one(doc)
    return str(result.inserted_id)


async def insert_scraped_doc(source: str, url: str, title: str, content: str) -> str:
    """Insert a scraped document into the 'scraped' collection.

    The actual write is delegated to _mongo_insert_one (circuit-breaker guarded)
    so repeated MongoDB failures open the circuit without mis-counting the
    'not connected' sentinel as a downstream failure.

    Args:
        source: Scraper source identifier (e.g., 'hn', 'jsonplaceholder').
        url: Canonical URL of the scraped page.
        title: Page or item title.
        content: Scraped text content.

    Returns:
        Inserted document ID as a string.

    Raises:
        RuntimeError: If the MongoDB client is not connected.
    """
    if _db is None:
        raise RuntimeError("MongoDB client not connected — ensure mongo_enabled=True")

    doc: dict[str, Any] = {
        "source": source,
        "url": url,
        "title": title,
        "content": content,
        "scraped_at": datetime.now(UTC).replace(tzinfo=None),
    }
    return await _mongo_insert_one(doc)


async def find_by_source(source: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return scraped documents filtered by source.

    Args:
        source: Scraper source identifier to filter by.
        limit: Maximum number of documents to return.

    Returns:
        List of document dicts (MongoDB _id serialized to string).
    """
    if _db is None:
        return []

    cursor = (
        _db[COLLECTION_SCRAPED]
        .find(
            {"source": source},
            {
                "_id": 1,
                "url": 1,
                "title": 1,
                "content": 1,
                "source": 1,
                "scraped_at": 1,
            },
        )
        .sort("scraped_at", -1)
        .limit(limit)
    )

    docs: list[dict[str, Any]] = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("scraped_at"), datetime):
            doc["scraped_at"] = doc["scraped_at"].isoformat()
        docs.append(doc)

    return docs
