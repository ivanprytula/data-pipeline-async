"""Shared fixtures for dashboard integration tests."""

import json
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import services.dashboard.routers.pages as pages
import services.dashboard.routers.sse as sse
from services.dashboard.main import app


_RECORD = {
    "id": 1,
    "source": "api.example.com",
    "timestamp": "2024-01-15T10:00:00",
    "data": {"value": 100},
    "tags": ["test"],
    "processed": False,
    "processed_at": None,
}

_RECORDS_RESPONSE = {
    "records": [_RECORD],
    "pagination": {"total": 1, "has_more": False},
}

_SEARCH_RESULT = {
    "id": 1,
    "source": "api.example.com",
    "timestamp": "2024-01-15T10:00:00",
    "score": 0.95,
}

_PROMETHEUS_RESPONSE = """# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total 1234.0
records_created_total 567.0
http_responses_total 890.0
"""


@dataclass
class FakeResponse:
    """Minimal async HTTP response used by dashboard upstream fakes."""

    status_code: int = 200
    json_data: dict[str, Any] | list[Any] | None = None
    text: str = ""

    def json(self) -> dict[str, Any] | list[Any]:
        return {} if self.json_data is None else self.json_data

    def raise_for_status(self) -> None:
        return None


class FakeAsyncClient:
    """Async HTTPX replacement for dashboard upstream calls."""

    def __init__(
        self,
        response: FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or FakeResponse()
        self.error = error

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
        if self.error is not None:
            raise self.error
        return self.response

    async def post(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
        if self.error is not None:
            raise self.error
        return self.response


class FakeSleep:
    """Track SSE sleep calls without actually waiting."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *_args: Any, **_kwargs: Any) -> None:
        self.calls += 1
        return None


@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[AsyncClient]:
    """Dashboard client fixture without database overrides."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture()
def records_response() -> dict[str, Any]:
    """Canonical dashboard records payload."""
    return _RECORDS_RESPONSE


@pytest.fixture()
def search_result() -> dict[str, Any]:
    """Canonical dashboard search result payload."""
    return _SEARCH_RESULT


@pytest.fixture()
def search_results_response(search_result: dict[str, Any]) -> dict[str, Any]:
    """Canonical dashboard search results envelope."""
    return {"results": [search_result]}


@pytest.fixture()
def prometheus_response() -> str:
    """Canonical Prometheus text payload for dashboard SSE tests."""
    return _PROMETHEUS_RESPONSE


@pytest.fixture()
def patch_pages_async_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., None]:
    """Patch the dashboard page router's upstream HTTP client."""

    def _patch(
        *,
        json_data: dict[str, Any] | list[Any] | None = None,
        error: Exception | None = None,
        status_code: int = 200,
        text: str = "",
    ) -> None:
        monkeypatch.setattr(
            pages.httpx,
            "AsyncClient",
            lambda *args, **kwargs: FakeAsyncClient(
                response=FakeResponse(
                    status_code=status_code,
                    json_data=json_data,
                    text=text,
                ),
                error=error,
            ),
        )

    return _patch


@pytest.fixture(autouse=True)
def _patch_pages_default_response(
    patch_pages_async_client: Callable[..., None],
    records_response: dict[str, Any],
) -> None:
    """Default dashboard page upstream response for happy-path tests."""
    patch_pages_async_client(json_data=records_response)


@pytest.fixture()
def patch_sse_async_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., None]:
    """Patch the dashboard SSE router's upstream HTTP client."""

    def _patch(
        *,
        text: str = _PROMETHEUS_RESPONSE,
        error: Exception | None = None,
        status_code: int = 200,
    ) -> None:
        monkeypatch.setattr(
            sse.httpx,
            "AsyncClient",
            lambda *args, **kwargs: FakeAsyncClient(
                response=FakeResponse(
                    status_code=status_code,
                    text=text,
                ),
                error=error,
            ),
        )

    return _patch


@pytest.fixture()
def sse_sleep(monkeypatch: pytest.MonkeyPatch) -> FakeSleep:
    """Patch SSE sleep to a reusable counter."""
    sleep = FakeSleep()
    monkeypatch.setattr(sse.asyncio, "sleep", sleep)
    return sleep


@pytest.fixture(autouse=True)
def _patch_sse_default_response(
    patch_sse_async_client: Callable[..., None],
    prometheus_response: str,
    sse_sleep: FakeSleep,
) -> None:
    """Default SSE upstream response and sleep counter for dashboard tests."""
    patch_sse_async_client(text=prometheus_response)


@pytest.fixture(autouse=True)
def _patch_sse_event_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the infinite SSE loop with a single-yield test generator."""

    async def _finite_metrics_event_generator() -> AsyncGenerator[str]:
        snapshot = await sse._scrape_metrics()
        yield f"data: {json.dumps(snapshot)}\n\n"
        await sse.asyncio.sleep(0)

    monkeypatch.setattr(
        sse, "_metrics_event_generator", _finite_metrics_event_generator
    )


@pytest.fixture()
def patch_sse_sleep(sse_sleep: FakeSleep) -> Callable[[], FakeSleep]:
    """Patch the SSE poll sleep to a fast counter."""

    def _patch() -> FakeSleep:
        return sse_sleep

    return _patch
