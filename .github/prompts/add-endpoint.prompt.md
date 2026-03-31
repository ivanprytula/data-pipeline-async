---
description: "Add a new API endpoint to this FastAPI project. Generates the CRUD function, Pydantic schemas, route, and integration tests in one pass — following this project's DbDep, structured logging, and asyncio_mode=auto conventions."
argument-hint: "Describe the endpoint, e.g. 'DELETE /api/v1/records/{id}' or 'GET /api/v1/records/stats — return count by source'"
agent: "agent"
---

You are adding a new API endpoint to this async FastAPI project. The argument is: **$ARGUMENTS**

Read [app/main.py](../app/main.py), [app/crud.py](../app/crud.py), [app/schemas.py](../app/schemas.py), [app/models.py](../app/models.py), and [tests/test_api.py](../tests/test_api.py) to understand the existing patterns before writing anything.

---

## Step 1 — Clarify design (if argument is ambiguous)

Before writing code, confirm:
- HTTP method and path (follow the existing `/api/v1/records/...` prefix)
- Request body, path params, or query params needed?
- Response shape — existing schema reusable, or new schema needed?
- Success status code (`200`, `201`, `204`?)
- Error cases (e.g. 404 if resource not found, 422 for validation)

If the argument is clear enough, proceed without asking.

---

## Step 2 — Add the CRUD function (`app/crud.py`)

Add a new `async` function. Rules:
- `AsyncSession` is always the **first positional argument**
- Return the ORM model (`Record | None`) or a plain value — never a schema from inside CRUD
- Use `select()` / `session.get()` / `session.execute()` — SQLAlchemy 2.0 style only
- Commit and `refresh` after mutations

```python
# Pattern for a mutating operation
async def my_operation(session: AsyncSession, record_id: int) -> Record | None:
    record = await session.get(Record, record_id)
    if record is None:
        return None
    # ... mutate ...
    await session.commit()
    await session.refresh(record)
    return record
```

---

## Step 3 — Add Pydantic schemas (`app/schemas.py`)

Only add new schemas if the existing ones (`RecordRequest`, `RecordResponse`, `RecordListResponse`) don't fit.

Rules:
- Keep request and response schemas separate
- Add `model_config = {"from_attributes": True}` on **response** schemas
- Use `Field(...)` for required fields with constraints (`min_length`, `ge`, `le`)
- Use `@field_validator` + `@classmethod` for cross-field or value validation

---

## Step 4 — Add the route (`app/main.py`)

Add the route in a clearly labelled section (match the existing comment style).

**Always use the `DbDep` type alias** — never inject `AsyncSession` directly:
```python
DbDep = Annotated[AsyncSession, Depends(get_db)]  # already defined at module level
```

Route pattern:
```python
@app.delete(
    "/api/v1/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["records"],
)
async def delete_record_endpoint(record_id: int, db: DbDep) -> None:
    cid = str(uuid.uuid4())
    logger.info("record_delete", extra={"id": record_id, "cid": cid})
    result = await delete_record(db, record_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    logger.info("record_deleted", extra={"id": record_id, "cid": cid})
```

Logging rules:
- Log **before** the DB call (request start) and **after** (success) using `python-json-logger` structured style
- First argument to `logger.info()` is an underscore-separated event name string
- Context goes in `extra={"cid": cid, ...}` — never in the message string

Update imports in `main.py` for the new CRUD function and any new schemas.

---

## Step 5 — Write integration tests (`tests/test_api.py`)

Tests use `aiosqlite` in-memory SQLite — no Postgres needed.

Rules:
- Do **NOT** add `@pytest.mark.asyncio` — `asyncio_mode = "auto"` handles it
- Use the `client: AsyncClient` fixture from `conftest.py`
- Reuse `_RECORD` fixture dict where possible, override specific fields with `{**_RECORD, "field": value}`

Write tests for:
1. **Happy path** — correct status code, expected response shape
2. **404 / not found** — when resource doesn't exist
3. **Validation errors (422)** — invalid input (if there's a request body or constrained params)

```python
# Pattern — happy path + 404
async def test_delete_record(client: AsyncClient) -> None:
    create = await client.post("/api/v1/records", json=_RECORD)
    record_id = create.json()["id"]
    r = await client.delete(f"/api/v1/records/{record_id}")
    assert r.status_code == 204

async def test_delete_record_not_found(client: AsyncClient) -> None:
    r = await client.delete("/api/v1/records/999999")
    assert r.status_code == 404
```

---

## Step 6 — Run tests

```bash
uv run pytest tests/ -v -k "<test_function_name>"
```

Fix any failures before finishing. Report the final test output.
