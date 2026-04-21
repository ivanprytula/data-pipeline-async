"""Kafka event consumer — processor service.

Phase 1: Subscribes to records.events topic, logs each event to stdout.
Phase 4: DLQ routing (3 retries → records.events.dlq) + OTel manual span.

Run standalone in Docker via: python main.py

Design notes:
- aiokafka AIOKafkaConsumer with auto_offset_reset="earliest" so events
  published before this service starts are not lost.
- Retry loop on startup: Redpanda may be slow to elect a leader after
  docker-compose brings it up, even after the healthcheck passes.
- Fail-open per message: malformed JSON is logged and skipped, not crashed.
- DLQ: after MAX_RETRIES processing failures the message is forwarded to
  TOPIC_DLQ so it can be inspected without blocking the main queue.
- SIGTERM handled by asyncio cancellation (docker stop sends SIGTERM).
- OTel: each consumed message creates a span with event metadata attributes.

Advanced Python here:
- ContextVar: trace_id propagated across the async consumer coroutine
  boundary so log records emitted during processing carry the trace ID.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextvars import ContextVar

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("processor")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BROKER_URL", "redpanda:29092")
TOPIC = "records.events"
TOPIC_DLQ = "records.events.dlq"
GROUP_ID = "processor-group"
MAX_RETRIES = 3

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "processor")

_RETRY_SLEEP_SECONDS = 5
_RETRY_MAX_ATTEMPTS = 12  # 60s total — Redpanda leader election can be slow

# ContextVar for trace_id: propagated into log extras within the consumer loop
current_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def _setup_otel():
    """Initialize OTel TracerProvider if enabled.

    Returns:
        A tracer instance, or None if OTel is disabled / unavailable.
    """
    if not OTEL_ENABLED:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource(attributes={"service.name": OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info(
            "otel_initialized endpoint=%s service=%s", OTEL_ENDPOINT, OTEL_SERVICE_NAME
        )
        return trace.get_tracer(OTEL_SERVICE_NAME)
    except Exception as exc:
        logger.warning("otel_init_failed error=%s", exc)
        return None


async def _send_to_dlq(
    producer: AIOKafkaProducer,
    raw_value: bytes,
    reason: str,
    partition: int,
    offset: int,
) -> None:
    """Forward a failed message to the dead letter queue topic.

    Args:
        producer: Live Kafka producer instance.
        raw_value: Original message bytes.
        reason: Human-readable failure description.
        partition: Source partition (for traceability).
        offset: Source offset (for traceability).
    """
    dlq_payload = json.dumps(
        {
            "source_topic": TOPIC,
            "source_partition": partition,
            "source_offset": offset,
            "reason": reason,
            "original": raw_value.decode(errors="replace"),
        }
    ).encode()
    try:
        await asyncio.wait_for(
            producer.send_and_wait(TOPIC_DLQ, value=dlq_payload),
            timeout=5.0,
        )
        logger.warning(
            "message_dlq_forwarded partition=%d offset=%d reason=%s",
            partition,
            offset,
            reason,
        )
    except TimeoutError:
        logger.error(
            "dlq_send_timeout partition=%d offset=%d",
            partition,
            offset,
        )
    except KafkaError as exc:
        logger.error("dlq_send_failed error=%s", exc)


async def _process_message(event: dict) -> None:
    """Business logic for a single consumed event.

    Args:
        event: Decoded event dict (must have 'event_type' and 'payload' keys).

    Raises:
        ValueError: If the event is missing required keys.
    """
    event_type = event.get("event_type")
    payload = event.get("payload")
    if event_type is None or payload is None:
        raise ValueError("event missing 'event_type' or 'payload'")
    logger.info(
        "event_processed event_type=%s payload=%s", event_type, json.dumps(payload)
    )


async def consume() -> None:
    """Main consumer loop: connect, consume indefinitely, then shutdown."""
    tracer = _setup_otel()

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)

    # Retry connection — Redpanda may not be ready immediately after healthcheck
    for attempt in range(1, _RETRY_MAX_ATTEMPTS + 1):
        try:
            await consumer.start()
            await producer.start()
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

    # Per-message retry state: (partition, offset) → attempt count
    retry_counts: dict[tuple[int, int], int] = {}

    try:
        async for msg in consumer:
            msg_key = (msg.partition, msg.offset)
            attempt = retry_counts.get(msg_key, 0) + 1

            # Start OTel span for this message (no-op when tracer is None)
            if tracer is not None:
                span_ctx = tracer.start_as_current_span(
                    "kafka.consume",
                    attributes={
                        "messaging.system": "kafka",
                        "messaging.destination": TOPIC,
                        "messaging.kafka.partition": msg.partition,
                        "messaging.kafka.offset": msg.offset,
                    },
                )
            else:
                span_ctx = _noop_span()

            with span_ctx:
                # Propagate trace_id into ContextVar for log correlation
                try:
                    from opentelemetry import trace as otel_trace

                    span = otel_trace.get_current_span()
                    ctx = span.get_span_context()
                    if ctx.is_valid:
                        current_trace_id.set(format(ctx.trace_id, "032x"))
                except Exception:
                    pass

                try:
                    event = json.loads(msg.value)
                    await _process_message(event)
                    # Successful — clear retry counter
                    retry_counts.pop(msg_key, None)
                except (json.JSONDecodeError, ValueError, KeyError) as exc:
                    logger.warning(
                        "event_decode_failed attempt=%d/%d error=%s raw=%r",
                        attempt,
                        MAX_RETRIES,
                        exc,
                        msg.value,
                    )
                    if attempt >= MAX_RETRIES:
                        await _send_to_dlq(
                            producer,
                            msg.value,
                            reason=str(exc),
                            partition=msg.partition,
                            offset=msg.offset,
                        )
                        retry_counts.pop(msg_key, None)
                    else:
                        retry_counts[msg_key] = attempt
    finally:
        await consumer.stop()
        await producer.stop()
        logger.info("consumer_stopped")


class _noop_span:
    """Minimal no-op context manager used when OTel is disabled."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


if __name__ == "__main__":
    asyncio.run(consume())
