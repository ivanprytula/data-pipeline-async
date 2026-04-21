from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncGenerator

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["sse"])

_INGESTOR_METRICS_URL = os.getenv("INGESTOR_URL", "http://localhost:8000") + "/metrics"
_POLL_INTERVAL_SECONDS = 5


@router.get("/metrics")
async def stream_metrics() -> StreamingResponse:
    """SSE endpoint — streams live Prometheus metric snapshots every 5 seconds."""
    return StreamingResponse(
        _metrics_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _metrics_event_generator() -> AsyncGenerator[str]:
    """Pull metrics from ingestor /metrics and yield SSE-formatted events."""
    while True:
        snapshot = await _scrape_metrics()
        payload = json.dumps(snapshot)
        yield f"data: {payload}\n\n"
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


async def _scrape_metrics() -> dict[str, str | int | float]:
    """Scrape the ingestor /metrics Prometheus endpoint and extract key counters."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(_INGESTOR_METRICS_URL)
            resp.raise_for_status()
            return _parse_prometheus_text(resp.text)
    except Exception as exc:
        logger.warning("metrics_scrape_failed", extra={"error": str(exc)})
        return {"error": "unavailable"}


def _parse_prometheus_text(text: str) -> dict[str, str | int | float]:
    """Extract a small set of counters from Prometheus text format."""
    counters: dict[str, str | int | float] = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name, value = parts[0], parts[1]
        # Surface the counters relevant to the dashboard
        if any(
            key in name
            for key in (
                "http_requests_total",
                "records_created_total",
                "http_responses_total",
            )
        ):
            with contextlib.suppress(ValueError):
                counters[name] = float(value)
    return counters
