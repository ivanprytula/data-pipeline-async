"""Integration tests for dashboard page routes."""

import re
from urllib.parse import urlparse

import pytest
from httpx import AsyncClient, HTTPError


# -----------------------------------------------------------------------
# Health & Readiness
# -----------------------------------------------------------------------
@pytest.mark.integration
async def test_health(client: AsyncClient) -> None:
    """Health endpoint returns 200."""
    r = await client.get("/health")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.integration
async def test_readyz(client: AsyncClient) -> None:
    """Readiness endpoint returns 200."""
    r = await client.get("/readyz")

    assert r.status_code == 200
    assert r.json()["status"] == "ready"


# -----------------------------------------------------------------------
# Records Explorer (/)
@pytest.mark.integration
async def test_index_page_returns_html(
    client: AsyncClient,
) -> None:
    """GET / returns HTML page."""
    r = await client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Records Explorer" in r.text


@pytest.mark.integration
async def test_index_page_with_source_filter(
    client: AsyncClient,
) -> None:
    """GET /?source=test filters records."""
    r = await client.get("/?source=test")

    assert r.status_code == 200
    assert "source" in r.text.lower()


@pytest.mark.integration
async def test_index_page_handles_ingestor_error(
    client: AsyncClient,
    patch_pages_async_client,
) -> None:
    """GET / gracefully handles ingestor unavailability."""
    patch_pages_async_client(error=HTTPError("Connection failed"))

    r = await client.get("/")

    assert r.status_code == 200
    assert "No records found" in r.text or "records" in r.text.lower()


# -----------------------------------------------------------------------
# Records Partial (HTMX infinite scroll)
@pytest.mark.integration
async def test_records_partial_returns_fragment(
    client: AsyncClient,
) -> None:
    """GET /partials/records returns HTML fragment for HTMX."""
    r = await client.get("/partials/records?skip=0")

    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "<table" in r.text


@pytest.mark.integration
async def test_records_partial_with_pagination(
    client: AsyncClient,
) -> None:
    """GET /partials/records respects skip and limit."""
    r = await client.get("/partials/records?skip=50&source=test")

    assert r.status_code == 200


@pytest.mark.integration
async def test_records_partial_invalid_skip_returns_422(client: AsyncClient) -> None:
    """GET /partials/records with invalid skip returns 422."""
    r = await client.get("/partials/records?skip=-1")

    assert r.status_code == 422


# -----------------------------------------------------------------------
# Semantic Search Page (/search)
# -----------------------------------------------------------------------
@pytest.mark.integration
async def test_search_page_returns_html(client: AsyncClient) -> None:
    """GET /search returns search page HTML."""
    r = await client.get("/search")

    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "search" in r.text.lower()


# -----------------------------------------------------------------------
# Search Partial (HTMX form submission)
@pytest.mark.integration
async def test_search_partial_returns_results(
    client: AsyncClient,
    patch_pages_async_client,
    search_results_response,
) -> None:
    """POST /partials/search returns search results HTML."""
    patch_pages_async_client(json_data=search_results_response)

    r = await client.post("/partials/search", data={"query": "startup"})

    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")

    urls = re.findall(r'https?://[^\s"\'<>]+', r.text)
    hosts = [urlparse(url).hostname for url in urls]
    assert "api.example.com" in hosts


@pytest.mark.integration
async def test_search_partial_empty_query_returns_422(client: AsyncClient) -> None:
    """POST /partials/search with empty query is rejected."""
    r = await client.post("/partials/search", data={"query": ""})

    assert r.status_code == 422


@pytest.mark.integration
async def test_search_partial_missing_query_returns_422(client: AsyncClient) -> None:
    """POST /partials/search without query field returns 422."""
    r = await client.post("/partials/search", data={})

    assert r.status_code == 422


@pytest.mark.integration
async def test_search_partial_handles_ai_gateway_error(
    client: AsyncClient,
    patch_pages_async_client,
) -> None:
    """POST /partials/search gracefully handles ai_gateway unavailability."""
    patch_pages_async_client(error=HTTPError("Gateway timeout"))

    r = await client.post("/partials/search", data={"query": "test"})

    assert r.status_code == 200
    assert "no matching records" in r.text.lower() or "enter a query" in r.text.lower()


# -----------------------------------------------------------------------
# Metrics Page (/metrics)
# -----------------------------------------------------------------------
@pytest.mark.integration
async def test_metrics_page_returns_html(client: AsyncClient) -> None:
    """GET /metrics returns metrics page HTML."""
    r = await client.get("/metrics")

    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "metrics" in r.text.lower()


@pytest.mark.integration
async def test_metrics_page_includes_sse_div(client: AsyncClient) -> None:
    """GET /metrics includes SSE-enabled div."""
    r = await client.get("/metrics")

    assert r.status_code == 200
    # Check for HTMX SSE attributes
    assert "hx-ext" in r.text or "sse" in r.text.lower()


# -----------------------------------------------------------------------
# Admin Page (/admin)
# -----------------------------------------------------------------------
@pytest.mark.integration
async def test_admin_page_returns_html(client: AsyncClient) -> None:
    """GET /admin returns admin workflows page."""
    r = await client.get("/admin")

    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Admin Workflows" in r.text


@pytest.mark.integration
async def test_admin_workers_health_partial_returns_fragment(
    client: AsyncClient,
    patch_pages_async_client,
) -> None:
    """GET /partials/admin/workers/health returns rendered worker health."""
    patch_pages_async_client(
        json_data={
            "running": True,
            "worker_count": 3,
            "queue_size": 1,
            "active_tasks": 1,
        }
    )

    r = await client.get("/partials/admin/workers/health")

    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Running" in r.text
    assert "True" in r.text


@pytest.mark.integration
async def test_admin_task_status_partial_returns_fragment(
    client: AsyncClient,
    patch_pages_async_client,
) -> None:
    """GET /partials/admin/tasks renders task lookup result."""
    patch_pages_async_client(
        json_data={
            "task_id": "task-1",
            "status": "succeeded",
            "batch_size": 4,
        }
    )

    r = await client.get("/partials/admin/tasks?task_id=task-1")

    assert r.status_code == 200
    assert "task-1" in r.text
    assert "succeeded" in r.text


@pytest.mark.integration
async def test_admin_manual_rerun_partial_returns_fragment(
    client: AsyncClient,
    patch_pages_async_client,
) -> None:
    """POST /partials/admin/rerun renders queued task details."""
    patch_pages_async_client(
        json_data={
            "task_id": "task-rerun-1",
            "status": "queued",
            "batch_size": 1,
        }
    )

    r = await client.post(
        "/partials/admin/rerun",
        data={"source": "admin.manual", "value": "123.4"},
    )

    assert r.status_code == 200
    assert "task-rerun-1" in r.text
    assert "queued" in r.text


@pytest.mark.integration
async def test_admin_session_partial_returns_fragment(
    client: AsyncClient,
    patch_pages_async_client,
) -> None:
    """POST /partials/admin/session renders created session details."""
    patch_pages_async_client(
        json_data={
            "session_id": "sess-123",
            "message": "Session created",
        }
    )

    r = await client.post(
        "/partials/admin/session",
        data={"user_id": "alice", "role": "writer"},
    )

    assert r.status_code == 200
    assert "sess-123" in r.text
    assert "writer" in r.text
