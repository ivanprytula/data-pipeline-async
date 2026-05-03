"""Webhook replay daemon — background task for re-publishing failed events.

The daemon runs in the FastAPI lifespan context as a long-running ``asyncio.Task``.
Every 5 minutes it queries the database for events with ``status='replay_queued'``,
attempts to re-publish each one to Kafka, and updates the status accordingly.

Cancellation: the task responds cleanly to ``asyncio.CancelledError`` on shutdown
so no events are left in an inconsistent state.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from services.webhook.constants import (
    WEBHOOK_EVENT_STATUS_FAILED,
    WEBHOOK_EVENT_STATUS_PUBLISHED,
)
from services.webhook.services.kafka_publisher import publish_webhook_event


logger = logging.getLogger(__name__)

_REPLAY_INTERVAL_SECONDS: int = 300  # 5 minutes
_REPLAY_BATCH_SIZE: int = 100


async def replay_loop() -> None:
    """Continuously check for replay-queued events and re-publish them to Kafka.

    Designed to run as a ``asyncio.Task`` started during FastAPI lifespan
    startup. Cancels gracefully on ``asyncio.CancelledError``.
    """
    logger.info(
        "replay_daemon_started", extra={"interval_seconds": _REPLAY_INTERVAL_SECONDS}
    )
    while True:
        try:
            await asyncio.sleep(_REPLAY_INTERVAL_SECONDS)
            await _run_replay_cycle()
        except asyncio.CancelledError:
            logger.info("replay_daemon_stopped")
            raise
        except Exception as exc:
            # Log and continue — do not crash the daemon on transient errors
            logger.error("replay_cycle_error", extra={"error": str(exc)})


async def _run_replay_cycle() -> None:
    """Execute a single replay cycle.

    Fetches up to ``_REPLAY_BATCH_SIZE`` events with ``status='replay_queued'``
    and attempts to re-publish each to Kafka using a fresh database session.
    """
    from services.webhook.core.database import AsyncSessionLocal
    from services.webhook.crud import (
        get_webhook_events_for_replay,
        update_webhook_event_status,
    )

    async with AsyncSessionLocal() as session:
        events = await get_webhook_events_for_replay(session, limit=_REPLAY_BATCH_SIZE)

    if not events:
        return

    logger.info("replay_cycle_begin", extra={"event_count": len(events)})
    succeeded = 0
    failed = 0

    for event in events:
        try:
            offset = await publish_webhook_event(
                source=event.source,
                event_id=event.id,
                delivery_id=event.delivery_id,
                payload=event.raw_payload or {},
            )

            async with AsyncSessionLocal() as session:
                if offset is not None:
                    await update_webhook_event_status(
                        session=session,
                        event_id=event.id,
                        status=WEBHOOK_EVENT_STATUS_PUBLISHED,
                        published_to_kafka=True,
                        kafka_offset=offset,
                        processed_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                    succeeded += 1
                else:
                    await update_webhook_event_status(
                        session=session,
                        event_id=event.id,
                        status=WEBHOOK_EVENT_STATUS_FAILED,
                        last_error="Kafka publish failed during replay",
                    )
                    failed += 1

        except Exception as exc:
            failed += 1
            logger.error(
                "replay_event_error",
                extra={"event_id": event.id, "source": event.source, "error": str(exc)},
            )
            try:
                async with AsyncSessionLocal() as session:
                    await update_webhook_event_status(
                        session=session,
                        event_id=event.id,
                        status=WEBHOOK_EVENT_STATUS_FAILED,
                        last_error=f"Replay error: {exc!s}",
                    )
            except Exception as inner_exc:
                logger.error(
                    "replay_status_update_error",
                    extra={"event_id": event.id, "error": str(inner_exc)},
                )

    logger.info(
        "replay_cycle_complete",
        extra={"succeeded": succeeded, "failed": failed},
    )
