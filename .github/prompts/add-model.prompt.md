---
description: "Add a new SQLAlchemy model and its full vertical slice: ORM model, Alembic migration reminder, CRUD module, Pydantic schemas, FastAPI router, and integration tests. Use when: adding a second resource, adding a new entity, creating a new model beyond Record."
argument-hint: "Describe the model, e.g. 'Pipeline with name (str), status (str: pending/running/done), and created_at'"
agent: "agent"
---

You are adding a **new SQLAlchemy model and its full vertical slice** to this async FastAPI + SQLAlchemy 2.0 project.

The new model is: **$ARGUMENTS**

Read [app/models.py](../app/models.py), [app/crud.py](../app/crud.py), [app/schemas.py](../app/schemas.py), [app/main.py](../app/main.py), [app/database.py](../app/database.py), and [tests/conftest.py](../tests/conftest.py) before writing anything.

---

## Step 1 — Design the model

Before writing code, confirm:
- Model name (singular, PascalCase): e.g. `Pipeline`
- Table name (plural, snake_case): e.g. `pipelines`
- Columns: name, type, nullable, default, constraints
- Indexes: which columns need individual or composite indexes?
- Any foreign keys to existing models?

If the argument is detailed enough, infer the design and proceed. State your assumptions explicitly.

---

## Step 2 — Add the ORM model (`app/models.py`)

Use **SQLAlchemy 2.0 style exclusively**. Never use legacy `Column()`.

```python
from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import UTC, datetime

class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )

    __table_args__ = (Index("idx_pipelines_status", "status"),)

    def __repr__(self) -> str:
        return f"<Pipeline id={self.id} name={self.name!r}>"
```

Column rules:
- `nullable=False` on all required columns — always explicit
- Timestamps: use `lambda: datetime.now(UTC).replace(tzinfo=None)` — strip `tzinfo` for asyncpg/aiosqlite compatibility
- `String(N)` with an explicit length — not bare `String`
- Composite indexes in `__table_args__`, single-column via `index=True`

---

## Step 3 — Alembic migration reminder

**Before running the app**, a migration must be created. Check if Alembic is configured:
- Does `alembic/` directory exist?
- Is `alembic` in `pyproject.toml` dependencies?

If yes, generate the migration:
```bash
uv run alembic revision --autogenerate -m "add_pipelines_table"
uv run alembic upgrade head
```

If Alembic is **not** configured, remind the user to run `/alembic-migration` first. Do not skip this step.

---

## Step 4 — Add a CRUD module (`app/crud_<modelname>.py`)

Create a **new file** `app/crud_pipelines.py` (don't add to `app/crud.py` — keep CRUD modules per resource).

Include at minimum: `create`, `get`, `list` (with pagination), and `delete`. Add others if the model warrants them.

```python
"""Async CRUD operations for Pipeline."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pipeline
from app.schemas import PipelineRequest  # add after schemas are created


async def create_pipeline(session: AsyncSession, request: PipelineRequest) -> Pipeline:
    pipeline = Pipeline(name=request.name, status=request.status)
    session.add(pipeline)
    await session.commit()
    await session.refresh(pipeline)
    return pipeline


async def get_pipeline(session: AsyncSession, pipeline_id: int) -> Pipeline | None:
    return await session.get(Pipeline, pipeline_id)


async def list_pipelines(
    session: AsyncSession, skip: int = 0, limit: int = 100
) -> tuple[list[Pipeline], int]:
    count_q = select(func.count()).select_from(Pipeline)
    data_q = select(Pipeline).order_by(Pipeline.id).offset(skip).limit(limit)
    total = (await session.execute(count_q)).scalar_one()
    pipelines = list((await session.execute(data_q)).scalars().all())
    return pipelines, total


async def delete_pipeline(session: AsyncSession, pipeline_id: int) -> Pipeline | None:
    pipeline = await session.get(Pipeline, pipeline_id)
    if pipeline is None:
        return None
    await session.delete(pipeline)
    await session.commit()
    return pipeline
```

---

## Step 5 — Add Pydantic schemas (`app/schemas.py`)

Add request and response schemas. Keep them separate. Response schemas need `from_attributes = True`.

```python
class PipelineRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="pending")

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        allowed = {"pending", "running", "done", "failed"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class PipelineResponse(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

---

## Step 6 — Add a FastAPI router (`app/routers/pipelines.py`)

Create `app/routers/` directory and a new router file. Do **not** add to `app/main.py` — use `APIRouter` to keep `main.py` clean as the project grows.

```python
"""Routes for /api/v1/pipelines."""

import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.crud_pipelines import create_pipeline, get_pipeline, list_pipelines, delete_pipeline
from app.schemas import PipelineRequest, PipelineResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_endpoint(request: PipelineRequest, db: DbDep) -> PipelineResponse:
    cid = str(uuid.uuid4())
    logger.info("pipeline_create", extra={"name": request.name, "cid": cid})
    pipeline = await create_pipeline(db, request)
    logger.info("pipeline_created", extra={"id": pipeline.id, "cid": cid})
    return pipeline  # type: ignore[return-value]
```

Then register the router in `app/main.py`:
```python
from app.routers import pipelines
app.include_router(pipelines.router)
```

Logging rules — same as existing endpoints:
- First arg to `logger.info()` is an underscore-separated event name
- All context in `extra={"cid": cid, ...}` — never interpolated into the message string

---

## Step 7 — Write integration tests (`tests/test_<modelname>.py`)

Create a **new test file** `tests/test_pipelines.py`. Reuse the `client` fixture from `conftest.py`.

Rules (same as all tests in this project):
- Do **NOT** add `@pytest.mark.asyncio` — `asyncio_mode = "auto"` handles it automatically
- Use `@pytest_asyncio.fixture()` for any async fixtures, not `@pytest.fixture()`
- Test: happy path, 404 / not found, 422 / validation error for each endpoint

```python
import pytest
from httpx import AsyncClient

_PIPELINE = {"name": "ingest-daily", "status": "pending"}


async def test_create_pipeline(client: AsyncClient) -> None:
    r = await client.post("/api/v1/pipelines", json=_PIPELINE)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "ingest-daily"
    assert body["id"] is not None


async def test_create_pipeline_invalid_status(client: AsyncClient) -> None:
    r = await client.post("/api/v1/pipelines", json={**_PIPELINE, "status": "unknown"})
    assert r.status_code == 422


async def test_get_pipeline_not_found(client: AsyncClient) -> None:
    r = await client.get("/api/v1/pipelines/99999")
    assert r.status_code == 404
```

---

## Step 8 — Run tests

```bash
uv run pytest tests/test_pipelines.py -v
```

Fix any failures before finishing. Report the final test output.
