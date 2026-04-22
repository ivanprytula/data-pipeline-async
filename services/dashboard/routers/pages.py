from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..constants import DEFAULT_PAGE_SIZE, INGESTOR_URL


logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(
    directory=str(os.path.join(os.path.dirname(__file__), "..", "templates"))
)


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    source: str | None = None,
    processed: bool = False,
) -> HTMLResponse:
    """Records Explorer page — full page render."""
    skip = 0
    records, has_more = await _fetch_records(
        skip=skip, source=source, processed=processed
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "active": "records",
            "records": records,
            "has_more": has_more,
            "next_skip": skip + DEFAULT_PAGE_SIZE,
            "source": source,
            "processed": processed,
        },
    )


@router.get("/partials/records", response_class=HTMLResponse)
async def records_partial(
    request: Request,
    skip: Annotated[int, Query(ge=0)] = 0,
    source: str | None = None,
    processed: bool = False,
) -> HTMLResponse:
    """HTMX partial — returns table rows only (used for infinite scroll + filter)."""
    records, has_more = await _fetch_records(
        skip=skip, source=source, processed=processed
    )
    return templates.TemplateResponse(
        request,
        "partials/records_rows.html",
        {
            "records": records,
            "has_more": has_more,
            "next_skip": skip + DEFAULT_PAGE_SIZE,
            "source": source,
            "processed": processed,
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request) -> HTMLResponse:
    """Semantic Search page — full page render (empty state)."""
    return templates.TemplateResponse(
        request,
        "search.html",
        {"active": "search"},
    )


@router.post("/partials/search", response_class=HTMLResponse)
async def search_partial(
    request: Request,
    query: Annotated[str, Form()],
) -> HTMLResponse:
    """HTMX partial — calls ai-gateway /search and returns results partial."""
    results = await _fetch_search_results(query)
    return templates.TemplateResponse(
        request,
        "partials/search_results.html",
        {"results": results},
    )


@router.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request) -> HTMLResponse:
    """Live Metrics page — full page render (SSE-driven)."""
    return templates.TemplateResponse(
        request,
        "metrics.html",
        {"active": "metrics"},
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    """Admin UI page with user/session and background-job workflows."""
    return templates.TemplateResponse(
        request,
        "admin.html",
        {"active": "admin"},
    )


@router.get("/partials/admin/workers/health", response_class=HTMLResponse)
async def admin_workers_health_partial(request: Request) -> HTMLResponse:
    """HTMX partial: worker-pool health summary."""
    health = await _fetch_workers_health()
    return templates.TemplateResponse(
        request,
        "partials/admin_workers_health.html",
        {"health": health},
    )


@router.get("/partials/admin/tasks", response_class=HTMLResponse)
async def admin_task_status_partial(
    request: Request,
    task_id: Annotated[str, Query(min_length=1)],
) -> HTMLResponse:
    """HTMX partial: one background task status lookup."""
    status_payload = await _fetch_task_status(task_id)
    return templates.TemplateResponse(
        request,
        "partials/admin_task_status.html",
        {"task": status_payload},
    )


@router.post("/partials/admin/rerun", response_class=HTMLResponse)
async def admin_manual_rerun_partial(
    request: Request,
    source: Annotated[str, Form(min_length=1)],
    value: Annotated[float, Form()],
) -> HTMLResponse:
    """HTMX partial: submit one-record batch ingest as manual rerun."""
    result = await _submit_manual_rerun(source=source, value=value)
    return templates.TemplateResponse(
        request,
        "partials/admin_rerun_result.html",
        {"result": result},
    )


@router.post("/partials/admin/session", response_class=HTMLResponse)
async def admin_create_session_partial(
    request: Request,
    user_id: Annotated[str, Form(min_length=1)],
    role: Annotated[str, Form(min_length=1)] = "viewer",
) -> HTMLResponse:
    """HTMX partial: create a v1 session for quick RBAC workflow checks."""
    result = await _create_session(user_id=user_id, role=role)
    return templates.TemplateResponse(
        request,
        "partials/admin_session_result.html",
        {"session": result},
    )


async def _fetch_records(
    *,
    skip: int = 0,
    source: str | None = None,
    processed: bool = False,
) -> tuple[list[dict], bool]:
    """Fetch records from ingestor API. Returns (records, has_more)."""
    params: dict[str, str | int] = {"skip": skip, "limit": DEFAULT_PAGE_SIZE}
    if source:
        params["source"] = source
    if processed:
        params["processed"] = "true"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{INGESTOR_URL}/api/v1/records", params=params)
            resp.raise_for_status()
            body = resp.json()
            items: list[dict] = (
                body.get("records", body) if isinstance(body, dict) else body
            )
            has_more = len(items) == DEFAULT_PAGE_SIZE
            return items, has_more
    except httpx.HTTPError as exc:
        logger.warning("ingestor_fetch_failed", extra={"error": str(exc)})
        return [], False


async def _fetch_search_results(query: str) -> list[dict]:
    """Call ai-gateway /search and return results list."""
    ai_gateway_url = os.getenv("AI_GATEWAY_URL", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ai_gateway_url}/search",
                json={"query": query, "top_k": 10},
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("results", [])
    except httpx.HTTPError as exc:
        logger.warning("ai_gateway_search_failed", extra={"error": str(exc)})
        return []


async def _fetch_workers_health() -> dict:
    """Fetch worker health from ingestor background endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{INGESTOR_URL}/api/v1/background/workers/health")
            resp.raise_for_status()
            body = resp.json()
            return body if isinstance(body, dict) else {"running": False}
    except httpx.HTTPError as exc:
        logger.warning("background_workers_health_failed", extra={"error": str(exc)})
        return {
            "running": False,
            "detail": "unavailable",
            "error": str(exc),
        }


async def _fetch_task_status(task_id: str) -> dict:
    """Fetch one background task status by ID from ingestor."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{INGESTOR_URL}/api/v1/background/tasks/{task_id}")
            resp.raise_for_status()
            body = resp.json()
            return body if isinstance(body, dict) else {"status": "unknown"}
    except httpx.HTTPError as exc:
        logger.warning("background_task_lookup_failed", extra={"error": str(exc)})
        return {
            "task_id": task_id,
            "status": "error",
            "detail": "task lookup failed",
            "error": str(exc),
        }


async def _submit_manual_rerun(*, source: str, value: float) -> dict:
    """Submit one-record batch ingest as a manual rerun workflow."""
    payload = {
        "records": [
            {
                "source": source,
                "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "data": {"value": value},
                "tags": ["admin-rerun"],
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{INGESTOR_URL}/api/v1/background/ingest/batch",
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body if isinstance(body, dict) else {"status": "queued"}
    except httpx.HTTPError as exc:
        logger.warning("manual_rerun_submit_failed", extra={"error": str(exc)})
        return {
            "status": "error",
            "detail": "manual rerun failed",
            "error": str(exc),
        }


async def _create_session(*, user_id: str, role: str) -> dict:
    """Create v1 session in ingestor for RBAC checks from admin UI."""
    normalized_role = role.strip().lower()
    if not normalized_role:
        normalized_role = "viewer"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{INGESTOR_URL}/api/v1/records/auth/login",
                params={"user_id": user_id, "role": normalized_role},
            )
            resp.raise_for_status()
            body = resp.json()
            if isinstance(body, dict):
                body["role"] = normalized_role
                return body
            return {"message": "session created", "role": normalized_role}
    except httpx.HTTPError as exc:
        logger.warning("admin_session_create_failed", extra={"error": str(exc)})
        return {
            "status": "error",
            "detail": "session creation failed",
            "error": str(exc),
            "role": normalized_role,
        }
