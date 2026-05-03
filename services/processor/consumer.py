"""Kafka consumer loop, ConsumerState, message processing, and DLQ routing.

Advanced Python patterns demonstrated here:
- ContextVar: trace_id propagated across the async consumer coroutine boundary
  so log records emitted during processing carry the trace ID.
- Dataclass: ConsumerState encapsulates mutable worker state without a class.
- Retry with ceiling: Redpanda leader election can take up to 60 s after
  docker-compose brings it up even when the healthcheck passes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from .constants import (
    _RETRY_MAX_ATTEMPTS,
    _RETRY_SLEEP_SECONDS,
    BOOTSTRAP_SERVERS,
    GROUP_ID,
    MAX_RETRIES,
    TOPIC,
    TOPIC_DLQ,
)
from .otel import setup_otel


logger = logging.getLogger(__name__)

# ContextVar for trace_id: propagated into log extras within the consumer loop
current_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


@dataclass
class ConsumerState:
    """Tracks the in-memory state of the Kafka consumer task.

    Single-instance worker: no coordination needed across replicas.
    Attributes are updated by the ``consume()`` coroutine and read by /readyz.
    """

    started: bool = False
    messages_consumed: int = 0
    messages_failed: int = 0
    last_event_ts: float | None = None
    task: asyncio.Task | None = field(default=None, repr=False)


class _noop_span:
    """Minimal no-op context manager used when OTel is disabled."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


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
            "message_dlq_forwarded",
            extra={"partition": partition, "offset": offset, "reason": reason},
        )
    except TimeoutError:
        logger.error(
            "dlq_send_timeout", extra={"partition": partition, "offset": offset}
        )
    except KafkaError as exc:
        logger.error("dlq_send_failed", extra={"error": str(exc)})


async def _process_message(event: dict) -> None:
    """Business logic for a single consumed event.

    Args:
        event: Decoded event dict (must have ``event_type`` and ``payload``).

    Raises:
        ValueError: When the event is missing required keys.
    """
    event_type = event.get("event_type")
    payload = event.get("payload")
    if event_type is None or payload is None:
        raise ValueError("event missing 'event_type' or 'payload'")
    logger.info(
        "event_processed",
        extra={"event_type": event_type, "payload": json.dumps(payload)},
    )


async def consume(state: ConsumerState) -> None:
    """Main consumer loop: connect, consume indefinitely, then shutdown.

    Args:
        state: Shared ``ConsumerState`` instance; updated as messages are consumed.
    """
    tracer = setup_otel()

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)

    # Retry — Redpanda may not be ready immediately after its healthcheck passes
    for attempt in range(1, _RETRY_MAX_ATTEMPTS + 1):
        try:
            await consumer.start()
            await producer.start()
            state.started = True
            logger.info(
                "consumer_started",
                extra={"topic": TOPIC, "servers": BOOTSTRAP_SERVERS},
            )
            break
        except KafkaError as exc:
            if attempt == _RETRY_MAX_ATTEMPTS:
                logger.error(
                    "consumer_connect_failed",
                    extra={"attempts": attempt, "error": str(exc)},
                )
                raise
            logger.warning(
                "consumer_retry",
                extra={
                    "attempt": attempt,
                    "max": _RETRY_MAX_ATTEMPTS,
                    "error": str(exc),
                    "sleep_s": _RETRY_SLEEP_SECONDS,
                },
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
                    from opentelemetry import trace as otel_trace  # noqa: PLC0415

                    span = otel_trace.get_current_span()
                    ctx = span.get_span_context()
                    if ctx.is_valid:
                        current_trace_id.set(format(ctx.trace_id, "032x"))
                except Exception:
                    pass

                try:
                    event = json.loads(msg.value)
                    await _process_message(event)
                    retry_counts.pop(msg_key, None)
                    state.messages_consumed += 1
                    state.last_event_ts = time.monotonic()
                except (json.JSONDecodeError, ValueError, KeyError) as exc:
                    state.messages_failed += 1
                    logger.warning(
                        "event_decode_failed",
                        extra={
                            "attempt": attempt,
                            "max": MAX_RETRIES,
                            "error": str(exc),
                        },
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


# Module-level singleton; started by main.py lifespan, read by routers/ops.py
state = ConsumerState()
