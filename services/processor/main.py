"""Kafka event consumer — processor service.

Phase 1: Subscribes to records.events topic, logs each event to stdout.

Run standalone in Docker via: python main.py

Design notes:
- aiokafka AIOKafkaConsumer with auto_offset_reset="earliest" so events
  published before this service starts are not lost.
- Retry loop on startup: Redpanda may be slow to elect a leader after
  docker-compose brings it up, even after the healthcheck passes.
- Fail-open per message: malformed JSON is logged and skipped, not crashed.
- SIGTERM handled by asyncio cancellation (docker stop sends SIGTERM).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("processor")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BROKER_URL", "redpanda:29092")
TOPIC = "records.events"
GROUP_ID = "processor-group"

_RETRY_SLEEP_SECONDS = 5
_RETRY_MAX_ATTEMPTS = 12  # 60s total — Redpanda leader election can be slow


async def consume() -> None:
    """Main consumer loop: connect, consume indefinitely, then shutdown."""
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
    )

    # Retry connection — Redpanda may not be ready immediately after healthcheck
    for attempt in range(1, _RETRY_MAX_ATTEMPTS + 1):
        try:
            await consumer.start()
            logger.info(
                "consumer_started topic=%s servers=%s", TOPIC, BOOTSTRAP_SERVERS
            )
            break
        except KafkaError as exc:
            if attempt == _RETRY_MAX_ATTEMPTS:
                logger.error(
                    "consumer_connect_failed attempts=%d error=%s", attempt, exc
                )
                raise
            logger.warning(
                "consumer_retry attempt=%d/%d error=%s sleeping=%ds",
                attempt,
                _RETRY_MAX_ATTEMPTS,
                exc,
                _RETRY_SLEEP_SECONDS,
            )
            await asyncio.sleep(_RETRY_SLEEP_SECONDS)

    try:
        async for msg in consumer:
            try:
                event = json.loads(msg.value)
                logger.info(
                    "event_received partition=%d offset=%d event=%s",
                    msg.partition,
                    msg.offset,
                    json.dumps(event),
                )
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("event_decode_failed error=%s raw=%r", exc, msg.value)
    finally:
        await consumer.stop()
        logger.info("consumer_stopped")


if __name__ == "__main__":
    asyncio.run(consume())
