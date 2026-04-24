"""Shared DTO contracts for cross-service API boundaries."""

from __future__ import annotations

from pydantic import BaseModel


class PaginationMeta(BaseModel):
    """Standard pagination metadata."""

    total: int
    skip: int
    limit: int
    has_more: bool


class NotificationDispatchResult(BaseModel):
    """One channel dispatch result for notification deliveries."""

    channel: str
    status: str
    detail: str


__all__ = ["PaginationMeta", "NotificationDispatchResult"]
