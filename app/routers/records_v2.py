"""Records v2 — advanced rate-limiting showcase.

This module exists as a side-by-side comparison with v1 (*the "before"*).

  v1  POST /api/v1/records           — fixed-window, IP-based (slowapi default)
  v2  POST /api/v2/records/token-bucket   — token bucket (burst-tolerant)
  v2  POST /api/v2/records/sliding-window — exact sliding window

The business logic (creating a record) is identical in every route.  Only the
rate-limiting strategy changes.  This makes the algorithmic difference the *only*
variable, which is useful for demos, benchmarks, and architecture discussions.

Observable difference
---------------------
Every v2 response carries these headers so clients (and interviewers) can
*see* the limiter state in real time:

  X-RateLimit-Limit     — configured maximum
  X-RateLimit-Remaining — requests still allowed in the current window/bucket
  X-RateLimit-Retry-After — seconds to wait on 429 (omitted when allowed)
  X-RateLimit-Strategy  — "token-bucket" or "sliding-window"

Try it with httpie:
    # Fire 15 rapid requests and watch the headers change
    for i in $(seq 1 15); do
        http POST :8000/api/v2/records/token-bucket source=demo \\
             timestamp=2024-01-15T10:00:00 data:='{"v":1}' tags:='[]'
    done
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from app.constants import (
    API_V2_PREFIX,
    JITTER_MAX_SECONDS,
    JITTER_MIN_SECONDS,
    SLIDING_WINDOW_LIMIT,
    SLIDING_WINDOW_SECONDS,
    TOKEN_BUCKET_CAPACITY,
    TOKEN_BUCKET_REFILL_PER_SEC,
)
from app.crud import create_record as create_record_op
from app.database import get_db
from app.rate_limiting_advanced import SlidingWindowLimiter, TokenBucketLimiter
from app.schemas import RecordRequest, RecordResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{API_V2_PREFIX}/records",
    tags=["records-v2 — advanced rate limiting"],
)

type DbDep = Annotated[AsyncSession, Depends(get_db)]

# ---------------------------------------------------------------------------
# Shared limiter instances — module-level singletons (per-process, in-memory).
# In production: construct once in lifespan() and inject via app.state or DI.
# ---------------------------------------------------------------------------

# Token bucket: burst up to TOKEN_BUCKET_CAPACITY, refill at TOKEN_BUCKET_REFILL_PER_SEC
# Great for: mobile apps, clients that batch requests occasionally
_token_bucket = TokenBucketLimiter(
    capacity=TOKEN_BUCKET_CAPACITY,
    refill_per_second=TOKEN_BUCKET_REFILL_PER_SEC,
)

# Sliding window: hard limit of SLIDING_WINDOW_LIMIT requests per SLIDING_WINDOW_SECONDS
# Great for: APIs where you need a *guaranteed* max rate, no burst exceptions
_sliding_window = SlidingWindowLimiter(
    limit=SLIDING_WINDOW_LIMIT,
    window_seconds=SLIDING_WINDOW_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_ip(request: Request) -> str:
    """Extract the best available client IP for rate-limit keying."""
    # Respect reverse-proxy headers first (nginx, ALB, Cloudflare)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _rl_headers(strategy: str, limit: int, remaining: float | int) -> dict[str, str]:
    """Build the standard rate-limit response headers."""
    return {
        "X-RateLimit-Strategy": strategy,
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(int(remaining)),
    }


# ---------------------------------------------------------------------------
# Token-bucket endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/token-bucket",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create record — token bucket rate limit",
    description=(
        "Identical to `POST /api/v1/records` but protected by a **token bucket**.\n\n"
        "**Algorithm**: each client IP owns a bucket of up to 20 tokens.  "
        "Tokens refill at 10/min (≈1 every 6 seconds).  Bursting is allowed "
        "until the bucket drains; after that requests are throttled at the refill "
        "rate.\n\n"
        "**v1 vs v2 difference**: v1 uses a *fixed window* (counter resets every "
        "minute, enabling a 2× burst at window boundaries).  Token bucket smooths "
        "that out.\n\n"
        "**Response headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, "
        "`X-RateLimit-Strategy`, `Retry-After` (on 429 only)."
    ),
)
async def create_record_token_bucket(
    request: Request,
    body: RecordRequest,
    db: DbDep,
    response: Response,
) -> RecordResponse:
    """Create a record — rate-limited via token bucket."""
    ip = _client_ip(request)
    allowed, remaining = await _token_bucket.consume(ip)

    if not allowed:
        retry_after = _token_bucket.seconds_until_token(
            ip, min_jitter=-JITTER_MIN_SECONDS, max_jitter=JITTER_MAX_SECONDS
        )
        logger.warning(
            "rate_limit_token_bucket",
            extra={"ip": ip, "retry_after": retry_after},
        )
        return JSONResponse(  # type: ignore[return-value]
            status_code=429,
            headers={
                **_rl_headers("token-bucket", _token_bucket.capacity, remaining),
                "Retry-After": str(int(retry_after) + 1),
            },
            content={"detail": "Rate limit exceeded (token bucket drained)"},
        )

    response.headers.update(
        _rl_headers("token-bucket", _token_bucket.capacity, remaining)
    )
    record = await create_record_op(db, body)
    return RecordResponse.model_validate(record)


# ---------------------------------------------------------------------------
# Sliding-window endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/sliding-window",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create record — sliding window rate limit",
    description=(
        "Identical to `POST /api/v1/records` but protected by a **sliding "
        "(rolling) window**.\n\n"
        "**Algorithm**: tracks the exact timestamps of the last N requests.  "
        "On each request the window `[now - 60 s, now]` is evaluated.  At most "
        "10 requests are allowed in any 60-second span, regardless of where the "
        "clock sits within a minute.\n\n"
        "**Fixed-window vulnerability this fixes**: a client can send 10 requests "
        "at 00:59 and 10 more at 01:01 — all 20 pass a fixed-window limiter.  "
        "Sliding window blocks the second batch because the first 10 are still in "
        "scope at 01:01.\n\n"
        "**Response headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, "
        "`X-RateLimit-Strategy`, `Retry-After` (on 429 only)."
    ),
)
async def create_record_sliding_window(
    request: Request,
    body: RecordRequest,
    db: DbDep,
    response: Response,
) -> RecordResponse:
    """Create a record — rate-limited via sliding window."""
    ip = _client_ip(request)
    allowed, remaining = await _sliding_window.is_allowed(ip)

    if not allowed:
        retry_after = _sliding_window.reset_in(
            ip, min_jitter=-JITTER_MIN_SECONDS, max_jitter=JITTER_MAX_SECONDS
        )
        logger.warning(
            "rate_limit_sliding_window",
            extra={"ip": ip, "retry_after": retry_after},
        )
        return JSONResponse(  # type: ignore[return-value]
            status_code=429,
            headers={
                **_rl_headers("sliding-window", _sliding_window.limit, remaining),
                "Retry-After": str(int(retry_after) + 1),
            },
            content={"detail": "Rate limit exceeded (sliding window full)"},
        )

    response.headers.update(
        _rl_headers("sliding-window", _sliding_window.limit, remaining)
    )
    record = await create_record_op(db, body)
    return RecordResponse.model_validate(record)
