# Week 2 Milestone 2: Pagination Deep-Dive

## Overview

Pagination is **crucial for scalability**. You don't want to load 1 million records into memory. Instead, you split them into pages and let the client navigate with `skip` and `limit`.

**API Endpoint:**

```text
GET /api/v1/records?skip=0&limit=100
```

**Response:**

```json
{
  "records": [ /* 100 records */ ],
  "pagination": {
    "total": 250,
    "skip": 0,
    "limit": 100,
    "has_more": true
  }
}
```

---

## Key Concepts Implemented

### 1. **Offset-based Pagination (Skip/Limit)**

The simplest form: use `skip` to skip N records, `limit` to take M records.

```python
# Database query
select(Record)
  .order_by(Record.id)
  .offset(skip)
  .limit(limit)
```

**Pros:**

- Simple to understand
- Works with any ordering
- Easy for UI (user can jump to "page 3")

**Cons:**

- Slow with large offsets (DB still scans N records, then skips)
- "Offset drift" if data changes between requests

**When to use:** Default choice for <1M records

### 2. **has_more Flag**

Calculate: `(skip + limit) < total`

```python
has_more = (skip + limit) < total
```

**Examples:**

- Total: 250, Skip: 0, Limit: 100 → has_more: True (100 < 250)
- Total: 250, Skip: 200, Limit: 100 → has_more: False (300 >= 250)
- Total: 250, Skip: 250, Limit: 100 → has_more: False (350 >= 250)

This tells the UI: "Is there a next page?" (essential for infinite scroll, pagination buttons)

### 3. **Default Limit**

```python
limit: Annotated[int, Query(ge=1, le=1000)] = 100
```

Default is 100, max is 1000. This prevents:

- Accidental full table loads (`?skip=0` without limit)
- Denial-of-service (`?skip=0&limit=999999999`)

### 4. **Cursor Preservation**

When you paginate forward, verify records don't overlap or have gaps:

```python
Page 1: skip=0, limit=10 → records [0-9]
Page 2: skip=10, limit=10 → records [10-19]
Page 3: skip=20, limit=10 → records [20-29]
```

Key: `skip` increases by exactly `limit`, so:

- No overlaps (same record in 2 pages)
- No gaps (missing records between pages)

---

## Test Coverage (5 New Tests)

### 1. **Multi-Page Traversal**

```text
test_pagination_multi_page_traversal
├─ Create 250 records
├─ Page 1: skip=0, limit=100 (has_more: True)
├─ Page 2: skip=100, limit=100 (has_more: True)
├─ Page 3: skip=200, limit=100 (has_more: False, only 50 records)
```

**Learning:** Partial pages are normal on the last page.

### 2. **Last Page Detection**

```text
test_pagination_last_page_detection
├─ Create 50 records
├─ Request: skip=0, limit=50
├─ Expect: has_more = False (all records fit in 1 page)
```

**Learning:** When all records fit in requested limit, has_more is False.

### 3. **Boundary Conditions**

```text
test_pagination_boundary_conditions
├─ Create 100 records
├─ Edge case 1: skip=99, limit=1 (last record, has_more: False)
├─ Edge case 2: skip=100, limit=10 (beyond all records, returns empty)
```

**Learning:** Handle skips at and beyond total count gracefully.

### 4. **Default Limit Behavior**

```text
test_pagination_default_limit
├─ Create 150 records
├─ Request: GET /api/v1/records (no limit param)
├─ Expect: limit=100 (default), has_more: True
```

**Learning:** Default limit prevents accidental full-table loads.

### 5. **Cursor Preservation**

```text
test_pagination_cursor_preservation
├─ Create 35 records
├─ Get page 1: IDs 0-9
├─ Get page 2: IDs 10-19
├─ Get page 3: IDs 20-29
├─ Get page 4: IDs 30-34
├─ Verify: All 35 unique, no gaps/overlaps
```

**Learning:** Pagination cursor must guarantee data integrity across requests.

---

## Code Pattern: Query with Pagination

From `app/crud.py`:

```python
async def get_records(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    source: str | None = None,
) -> tuple[list[Record], int]:
    # Count total (no skip/limit)
    count_q = select(func.count()).select_from(Record).where(Record.deleted_at.is_(None))

    # Fetch paginated data
    data_q = (
        select(Record)
        .where(Record.deleted_at.is_(None))
        .order_by(Record.id)
        .offset(skip)
        .limit(limit)
    )

    # Apply filter if provided
    if source:
        count_q = count_q.where(Record.source == source)
        data_q = data_q.where(Record.source == source)

    # Execute both
    total = (await session.execute(count_q)).scalar_one()
    records = list((await session.execute(data_q)).scalars().all())
    return records, total
```

**Key pattern:**

1. Count total (respects filters)
2. Fetch paginated slice (respects skip/limit)
3. Return both (client calculates `has_more`)

---

## Route Handler: Convert to Response

From `app/routers/records.py`:

```python
@router.get("", response_model=RecordListResponse)
async def list_records(
    db: DbDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    source: str | None = None,
) -> RecordListResponse:
    records, total = await get_records(db, skip, limit, source)
    return RecordListResponse(
        records=records,
        pagination=PaginationMeta(
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + limit) < total,
        ),
    )
```

**Key points:**

- Input validation: `skip >= 0`, `1 <= limit <= 1000`
- Calculate `has_more` at response time
- Client receives all info needed for next request

---

## Interview Talking Points

After Week 2 Milestone 2, you can discuss:

1. **Why pagination is essential:**
   - "Loading all records into memory doesn't scale"
   - "250 records is fine; 250M records is not"
   - Example: Twitter's feed—billions of records, paginated

2. **Offset vs cursor-based pagination:**
   - Offset (what we use): simple, but slow with large offsets
   - Cursor: faster for large datasets, but requires sorting by unique field

3. **has_more flag vs page numbers:**
   - Has_more: "Is there another page?" (used by infinite scroll)
   - Page numbers: "Jump to page 5" (used by traditional pagination UI)

4. **Edge cases you handle:**
   - Skip beyond total (return empty, not error)
   - Partial last page (fewer records than limit)
   - Large skip values (test if performance degrades)

5. **Why you test boundaries:**
   - "I test at_limit, beyond_limit, and zero_limit"
   - "Edge cases reveal assumptions in code"

---

## Next: Immediate Actions

1. **Run the tests:**

   ```bash
   uv run pytest tests/integration/records/test_api.py -k pagination -v
   ```

2. **Try pagination via Swagger:**

   ```bash
   uv run uvicorn app.main:app --reload
   # Visit http://localhost:8000/docs
   # Test: GET /api/v1/records?skip=0&limit=10
   ```

3. **Load-test pagination:**

   ```bash
   # Create 10k records, test if offset becomes slow
   # (This is Week 3 optimization work)
   ```

4. **Study alternative patterns:**
   - Cursor-based pagination (more efficient, harder to implement)
   - Keyset pagination (timestamp-based, good for real-time data)

---

## Success Criteria for Milestone 2

- [x] Pagination endpoint works (`GET /api/v1/records?skip=X&limit=Y`)
- [x] `has_more` flag is accurate
- [x] Multi-page traversal tested (250+ records)
- [x] Edge cases tested (boundary conditions, empty results)
- [x] Default limit tested (100 when omitted)
- [x] Cursor preservation verified (no gaps/overlaps)
- [x] All 31 tests passing
- [x] Commit: `235db80`

---

## Week 2 Progress

| Milestone           | Status | Tests | Patterns                                      |
| ------------------- | ------ | ----- | --------------------------------------------- |
| 1. Batch Operations | ✅      | 3     | Bulk insert, `add_all()`, `refresh()`        |
| 2. Pagination       | ✅      | 6     | Offset/limit, `has_more`, cursor preservation|
| 3. Rate Limiting    | ⏳      | —     | slowapi, 429 responses                       |
| 4. Error Handling   | ⏳      | —     | Exponential backoff, retry logic             |
| 5. Validation       | ⏳      | —     | Pydantic validators, field_validator         |
| 6. API Docs         | ⏳      | —     | Swagger UI, OpenAPI schema                   |

**Sprint Velocity:** 2/6 milestones complete. On track for Week 2 completion.
