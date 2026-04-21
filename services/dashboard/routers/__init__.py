from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix="/sse", tags=["sse"])

__all__ = ["router"]
