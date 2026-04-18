"""Async Kafka event producer — fail-open on connection errors.

Modeled on app/cache.py singleton pattern:
- Module-level _producer singleton
- connect_producer() / disconnect_producer() for lifespan wiring
- All operations are pure async, fail-open on KafkaError

Advanced Python patterns demonstrated:
- TypeVar + Generic: EventPayload[T] typed event envelope (Phase 1 spec)
- Observer pattern: publish_record_created called from records router
  after successful DB write (record creation triggers the event)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError


# ---------------------------------------------------------------------------
# Generic event envelope (PEP 695 syntax — Python 3.12+ standard)
# ---------------------------------------------------------------------------


class EventPayload[T]:
    """Typed event envelope — wraps any payload with a named event_type.

    Generic over T so callers get type-checked payloads:

        event: EventPayload[dict[str, Any]] = EventPayload(
            event_type="record.created",
            payload={"record_id": 1, "source": "api"},
        )
        msg_bytes = json.dumps(event.to_dict()).encode()

    The Observer pattern connects producers (this module) to consumers
    (services/processor) via the Kafka topic without direct coupling.
    """

    def __init__(self, event_type: str, payload: T) -> None:
        self.event_type = event_type
        self.payload = payload

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-encodable dict."""
        return {"event_type": self.event_type, "payload": self.payload}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOPIC_RECORD_CREATED = "records.events"


# ---------------------------------------------------------------------------
# Module-level singleton (initialized in lifespan startup)
# ---------------------------------------------------------------------------
_producer: AIOKafkaProducer | None = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifecycle helpers (called from app/main.py lifespan)
# ---------------------------------------------------------------------------
async def connect_producer(bootstrap_servers: str) -> None:
    """Initialize and start the Kafka producer.

    Args:
        bootstrap_servers: Comma-separated Kafka bootstrap brokers.

    Raises:
        KafkaError: If broker is unreachable (propagated to caller for logging).
    """
    global _producer
    _producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
    assert _producer is not None  # type safety check
    await _producer.start()
    logger.info("kafka_producer_connected", extra={"servers": bootstrap_servers})


async def disconnect_producer() -> None:
    """Stop and clean up the Kafka producer."""
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
    logger.info("kafka_producer_disconnected")


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------
async def publish_record_created(record_id: int, payload: dict[str, Any]) -> None:
    """Publish a record.created event to TOPIC_RECORD_CREATED.

    Fail-open: KafkaError is logged as a warning; the request is never failed.
    If the producer is not connected (kafka_enabled=False), this is a no-op.

    Args:
        record_id: Primary key of the newly created record.
        payload: Additional record fields to include in the event.
    """
    if _producer is None:
        return

    event: EventPayload[dict[str, Any]] = EventPayload(
        event_type="record.created",
        payload={"record_id": record_id, **payload},
    )

    try:
        await _producer.send_and_wait(
            TOPIC_RECORD_CREATED,
            value=json.dumps(event.to_dict()).encode(),
        )
        logger.debug(
            "event_published",
            extra={"event_type": "record.created", "record_id": record_id},
        )
    except KafkaError as exc:
        logger.warning(
            "kafka_publish_failed",
            extra={"error": str(exc), "record_id": record_id},
        )
