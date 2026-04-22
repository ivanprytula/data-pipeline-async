"""Project-wide constants — single source of truth for every magic value.

Rule: no bare integer or string literal in route handlers, CRUD functions,
schemas, or models. Import the name from here instead.

Grouping
--------
- API prefixes / versioning
- Pagination / query limits
- Batch operation limits
- Field-level validation bounds
- Rate-limiting parameters (v1 fixed-window, v2 token-bucket, v2 sliding-window)
"""

# ---------------------------------------------------------------------------
# API routing
# ---------------------------------------------------------------------------
API_V1_PREFIX: str = "/api/v1"
API_V2_PREFIX: str = "/api/v2"

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE: int = 100
MAX_PAGE_SIZE: int = 1000

# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------
MAX_BATCH_SIZE: int = 1000  # records per /batch request
MIN_BATCH_SIZE: int = 1

# ---------------------------------------------------------------------------
# Record field validation
# ---------------------------------------------------------------------------
SOURCE_MAX_LENGTH: int = 255
SOURCE_MIN_LENGTH: int = 1
TAGS_MAX_COUNT: int = 10

# ---------------------------------------------------------------------------
# Rate limiting — v1 fixed-window (slowapi)
# ---------------------------------------------------------------------------
V1_RATE_LIMIT: str = "1000/minute"
HEALTH_RATE_LIMIT: str = "100/minute"

# ---------------------------------------------------------------------------
# Rate limiting — v2 token bucket
# ---------------------------------------------------------------------------
TOKEN_BUCKET_CAPACITY: int = 20  # max burst size (tokens)
TOKEN_BUCKET_REFILL_PER_SEC: float = 10 / 60  # 10 requests per minute → ≈0.167/s

# ---------------------------------------------------------------------------
# Rate limiting — v2 sliding window
# ---------------------------------------------------------------------------
SLIDING_WINDOW_LIMIT: int = 10  # max requests in the window
SLIDING_WINDOW_SECONDS: int = 60  # rolling window size
# ---------------------------------------------------------------------------
# Retry-After jitter (thundering herd prevention)
# ---------------------------------------------------------------------------
JITTER_MIN_SECONDS: float = 5.0  # minimum random offset
JITTER_MAX_SECONDS: float = 10.0  # maximum random offset

# ---------------------------------------------------------------------------
# Concurrent enrichment (Step 8)
# ---------------------------------------------------------------------------
ENRICH_SEMAPHORE_LIMIT: int = 10  # cap concurrent external API calls
ENRICH_MAX_IDS: int = 50  # max record IDs per /enrich request
ENRICH_MIN_IDS: int = 1  # min record IDs per /enrich request

# ---------------------------------------------------------------------------
# Idempotent upsert (Step 9)
# ---------------------------------------------------------------------------
UPSERT_MODE_IDEMPOTENT: str = "idempotent"  # 201 on create, 200 on conflict
UPSERT_MODE_STRICT: str = "strict"  # 201 on create, 409 on conflict

# ---------------------------------------------------------------------------
# Caching — Redis
# ---------------------------------------------------------------------------
CACHE_KEY_RECORD: str = "dp:record:{record_id}"  # Redis key namespace
CACHE_TTL_RECORD: int = 3600  # 1 hour — single records are stable

# ---------------------------------------------------------------------------
# Background workers (Pillar 5)
# ---------------------------------------------------------------------------
BACKGROUND_WORKER_COUNT_DEFAULT: int = 2
BACKGROUND_WORKER_QUEUE_SIZE_DEFAULT: int = 200
BACKGROUND_MAX_TRACKED_TASKS_DEFAULT: int = 500
