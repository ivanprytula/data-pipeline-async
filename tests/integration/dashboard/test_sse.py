"""Integration tests for dashboard SSE endpoints."""

import pytest
from httpx import AsyncClient


# -----------------------------------------------------------------------
# SSE Metrics Streaming
# -----------------------------------------------------------------------
@pytest.mark.integration
async def test_sse_metrics_returns_stream(
    client: AsyncClient,
) -> None:
    """GET /sse/metrics returns Server-Sent Events stream."""
    async with client.stream("GET", "/sse/metrics") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert "no-cache" in response.headers.get("cache-control", "").lower()
        assert response.headers.get("x-accel-buffering") == "no"

        lines: list[str] = []
        async for line in response.aiter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 1:
                break

    assert lines and lines[0].startswith("data:")


@pytest.mark.integration
async def test_sse_metrics_response_contains_data_lines(
    client: AsyncClient,
) -> None:
    """SSE stream yields data: lines in JSON format."""
    async with client.stream("GET", "/sse/metrics") as response:
        assert response.status_code == 200
        text = ""
        async for line in response.aiter_lines():
            if line:
                text = line
                break

    assert text.startswith("data:")
    assert "{" in text


@pytest.mark.integration
async def test_sse_metrics_handles_scrape_error(
    client: AsyncClient,
    patch_sse_async_client,
) -> None:
    """SSE stream continues even if Prometheus scrape fails temporarily."""
    patch_sse_async_client(error=RuntimeError("Timeout"))

    async with client.stream("GET", "/sse/metrics") as response:
        assert response.status_code == 200
        text = ""
        async for line in response.aiter_lines():
            if line:
                text = line
                break

    assert text.startswith("data:")
    assert "unavailable" in text or "error" in text


@pytest.mark.integration
async def test_sse_metrics_polls_at_interval(
    client: AsyncClient,
    sse_sleep,
) -> None:
    """SSE stream respects poll interval (5 second default)."""
    # This test verifies the structure, not timing (timing in unit tests)
    async with client.stream("GET", "/sse/metrics") as response:
        assert response.status_code == 200
        lines = []
        async for line in response.aiter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 2:
                break

    assert len(lines) >= 1
    assert sse_sleep.calls >= 1
