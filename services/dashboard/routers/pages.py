from __future__ import annotations

import logging
import os
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
        "index.html",
        {
            "request": request,
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
        "partials/records_rows.html",
        {
            "request": request,
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
        "search.html",
        {"request": request, "active": "search"},
    )


@router.post("/partials/search", response_class=HTMLResponse)
async def search_partial(
    request: Request,
    query: Annotated[str, Form()],
) -> HTMLResponse:
    """HTMX partial — calls ai-gateway /search and returns results partial."""
    results = await _fetch_search_results(query)
    return templates.TemplateResponse(
        "partials/search_results.html",
        {"request": request, "results": results},
    )


@router.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request) -> HTMLResponse:
    """Live Metrics page — full page render (SSE-driven)."""
    return templates.TemplateResponse(
        "metrics.html",
        {"request": request, "active": "metrics"},
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
