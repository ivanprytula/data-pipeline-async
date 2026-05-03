"""Async Kafka publisher for webhook events.

Fire-and-forget pattern: the HTTP handler returns 202 immediately
while this module publishes to Kafka asynchronously. Publish errors are
logged and recorded in the audit log (``webhook_events.status = 'failed'``)
but do not affect the HTTP response status.

Topic naming convention: ``webhook.events.{source}``
Partition key: ``source`` (ensures delivery-order per source).
"""

from __future__ import annotations

import logging
import os
from typing import Any


logger = logging.getLogger(__name__)

_KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL", "localhost:9092")
_KAFKA_TOPIC_PREFIX = "webhook.events"

# Module-level producer singleton — initialised lazily on first publish
_producer = None


async def _get_producer():
    """Return (or create) the shared AIOKafkaProducer singleton."""
    global _producer  # noqa: PLW0603
    if _producer is not None:
        return _producer
    try:
        from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]

        producer = AIOKafkaProducer(
            bootstrap_servers=_KAFKA_BROKER_URL,
            value_serializer=lambda v: __import__("json").dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await producer.start()
        _producer = producer
        logger.info("kafka_producer_started", extra={"broker": _KAFKA_BROKER_URL})
        return _producer
    except ImportError:
        logger.warning("aiokafka_not_installed", extra={"broker": _KAFKA_BROKER_URL})
        return None


async def stop_producer() -> None:
    """Flush pending messages and stop the producer cleanly on service shutdown."""
    global _producer  # noqa: PLW0603
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("kafka_producer_stopped")


async def publish_webhook_event(
    source: str,
    event_id: int,
    delivery_id: str,
    payload: dict[str, Any],
) -> int | None:
    """Publish a webhook event to the Kafka topic for this source.

    Args:
        source: Webhook source name (e.g., ``'stripe'``).
        event_id: Database ID of the ``webhook_events`` row.
        delivery_id: Unique webhook delivery ID.
        payload: Raw webhook payload dict.

    Returns:
        Kafka message offset on success, ``None`` on failure.
    """
    topic = f"{_KAFKA_TOPIC_PREFIX}.{source}"
    message: dict[str, Any] = {
        "event_id": event_id,
        "delivery_id": delivery_id,
        "source": source,
        "payload": payload,
    }

    producer = await _get_producer()
    if producer is None:
        logger.warning(
            "kafka_publish_skipped",
            extra={"source": source, "reason": "producer unavailable"},
        )
        return None

    try:
        record_metadata = await producer.send_and_wait(
            topic=topic,
            value=message,
            key=source,
        )
        logger.info(
            "kafka_webhook_published",
            extra={
                "source": source,
                "event_id": event_id,
                "topic": topic,
                "offset": record_metadata.offset,
            },
        )
        return record_metadata.offset
    except Exception as exc:
        logger.error(
            "kafka_publish_failed",
            extra={"source": source, "event_id": event_id, "error": str(exc)},
        )
        return None


async def is_kafka_healthy() -> bool:
    """Check whether the Kafka producer can reach the broker.

    Used by the ``/readyz`` health endpoint. Returns ``True`` if a producer
    can be obtained (even if idle), ``False`` otherwise.
    """
    producer = await _get_producer()
    return producer is not None
