"""libs.contracts — shared data contracts across service boundaries.

Intended contents (define in Phase 3, services adopt in Phase 4):
- events     : domain event envelopes (RecordIngested, RecordProcessed, …)
- schemas    : shared Pydantic v2 request/response DTOs used by >1 service
- types      : common type aliases and enumerations (RecordStatus, SourceType, …)
- pagination : standard paginated response wrapper

Design constraints:
- Pydantic v2 only; no SQLAlchemy ORM types (those stay in each service)
- No imports from any service (ingestor, services/*)
- May import from libs.platform only for logging helpers
- Keep modules small and focused — one concept per file

Usage pattern (once populated):
    from libs.contracts.events import RecordIngested
    from libs.contracts.schemas import PaginatedResponse
    from libs.contracts.types import RecordStatus
"""

from libs.contracts.events import (
    EVENT_DOC_SCRAPED,
    EVENT_RECORD_CREATED,
    TOPIC_RECORD_CREATED,
    TOPIC_SCRAPED,
    EventPayload,
)
from libs.contracts.schemas import NotificationDispatchResult, PaginationMeta


__all__ = [
    "EventPayload",
    "EVENT_RECORD_CREATED",
    "EVENT_DOC_SCRAPED",
    "TOPIC_RECORD_CREATED",
    "TOPIC_SCRAPED",
    "PaginationMeta",
    "NotificationDispatchResult",
]
