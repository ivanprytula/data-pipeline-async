"""Resource initialization and lifespan management for external services.

Encapsulates startup/shutdown logic for:
- Redis cache (optional)
- Kafka producer (optional)
- MongoDB (optional)

Design principle: Each service is independently initializable and gracefully
degrades if unavailable (fail-open for optional services).
"""

from __future__ import annotations

import logging

from ingestor import cache, events
from ingestor.config import settings
from ingestor.storage import mongo


logger = logging.getLogger(__name__)


async def initialize_external_services() -> None:
    """Initialize all optional external services during app startup.

    Services are initialized in order of dependency:
    1. Redis (for caching)
    2. Kafka (for events)
    3. MongoDB (for storage)

    Each service failure is logged but non-fatal (fail-open).
    """

    # Initialize Redis cache (optional)
    if settings.redis_enabled:
        try:
            await cache.connect_cache(settings.redis_url)
            logger.info(
                "cache_connected",
                extra={"service": "redis", "url": settings.redis_url},
            )
        except Exception as e:
            logger.warning(
                "cache_connection_failed",
                extra={"service": "redis", "error": str(e)},
            )
            # Non-fatal: cache is optional, app continues without it

    # Initialize Kafka producer (optional)
    if settings.kafka_enabled:
        try:
            await events.connect_producer(settings.kafka_broker_url)
            logger.info(
                "events_producer_connected",
                extra={"service": "kafka", "broker": settings.kafka_broker_url},
            )
        except Exception as e:
            logger.warning(
                "events_producer_connection_failed",
                extra={"service": "kafka", "error": str(e)},
            )
            # Non-fatal: events are fail-open, app continues without broker

    # Initialize MongoDB (optional)
    if settings.mongo_enabled:
        try:
            await mongo.connect_mongo(settings.mongo_url, settings.mongo_db_name)
            logger.info(
                "mongo_connected",
                extra={"service": "mongodb", "db": settings.mongo_db_name},
            )
        except Exception as e:
            logger.warning(
                "mongo_connection_failed",
                extra={"service": "mongodb", "error": str(e)},
            )
            # Non-fatal: scraper routes degrade gracefully without MongoDB


async def cleanup_external_services() -> None:
    """Cleanup all external services during app shutdown.

    Cleanup order (LIFO from initialization):
    1. Kafka producer
    2. Redis cache
    3. MongoDB

    Each cleanup is attempted even if a prior step fails.
    """

    # Cleanup Kafka (safe even if not connected)
    try:
        await events.disconnect_producer()
        logger.info("events_producer_disconnected")
    except Exception as e:
        logger.warning(
            "events_producer_cleanup_error",
            extra={"error": str(e)},
        )

    # Cleanup Redis (safe even if not connected)
    try:
        await cache.disconnect_cache()
        logger.info("cache_disconnected")
    except Exception as e:
        logger.warning(
            "cache_cleanup_error",
            extra={"error": str(e)},
        )

    # Cleanup MongoDB (safe even if not connected)
    try:
        await mongo.disconnect_mongo()
        logger.info("mongo_disconnected")
    except Exception as e:
        logger.warning(
            "mongo_cleanup_error",
            extra={"error": str(e)},
        )
