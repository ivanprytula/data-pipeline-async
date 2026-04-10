# Pillar 2: Database (PostgreSQL + SQLAlchemy)

**Tier**: Foundation (🟢) + Middle (🟡) + Senior (🔴)  
**Project**: Critical for most backend roles  
**Building in**: `data-pipeline-async` / `app/models.py`, `app/database.py`, `app/crud.py`

---

## Foundation (🟢)

### SQL You Must Write from Memory

#### `JOIN` Types: INNER, LEFT, CROSS — When to Use Each

**What it is**:

- `INNER JOIN`: rows that match in BOTH tables
- `LEFT JOIN`: all rows from left table + matching rows from right
- `CROSS JOIN`: Cartesian product (every left × every right)

**When to use**:

- **INNER**: "Get users who have orders" (both must match)
- **LEFT**: "Get all users and their order count (null if 0)" (all users, even no orders)
- **CROSS**: rare; e.g., generate date ranges × categories

**Example**:

```sql
-- INNER: only matching
SELECT u.id, u.name, o.id, o.total
FROM users u
INNER JOIN orders o ON u.id = o.user_id;

-- LEFT: all users, null if no orders
SELECT u.id, u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name;

-- CROSS: every combo
SELECT d.date, c.category
FROM (SELECT CURRENT_DATE + interval '1 day' * i as date FROM generate_series(0, 30) i) d
CROSS JOIN (SELECT DISTINCT category FROM products) c;
```

---

### SQLAlchemy 2.0 ORM

#### `mapped_column`, `Mapped[T]`, `relationship`, `ForeignKey`

**What it is**:

- `mapped_column(primary_key=True)` = define column
- `Mapped[int]` = type hint style (SQLAlchemy 2.0 preferred)
- `relationship()` = define association to another model
- `ForeignKey()` = constraint + navigation

**Example**:

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Record(Base):
    __tablename__ = "records"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(nullable=False)
    processed: Mapped[bool] = mapped_column(default=False)
    processed_at: Mapped[str | None] = mapped_column(default=None)
    data: Mapped[dict] = mapped_column(type_=JSON, default_factory=dict)
```

---

#### `select()`, `where()`, `scalar_one_or_none()`, `scalars().all()`

**What it is**:

- `select(Model)` = build SQL SELECT query
- `where()` = add WHERE clause
- `scalar_one_or_none()` = fetch single row, return model or None
- `scalars().all()` = fetch all rows, return list of models

**Example**:

```python
from sqlalchemy import select

async def get_record(db: AsyncSession, record_id: int) -> Record | None:
    """Get one record by ID."""
    stmt = select(Record).where(Record.id == record_id)
    return await db.scalar_one_or_none(stmt)

async def list_records(db: AsyncSession, limit: int = 10) -> list[Record]:
    """List all records."""
    stmt = select(Record).limit(limit)
    return await db.scalars(stmt).all()

async def list_processed(db: AsyncSession) -> list[Record]:
    """List only processed records."""
    stmt = select(Record).where(Record.processed == True)
    return await db.scalars(stmt).all()
```

---

### Alembic Migrations

#### `alembic revision --autogenerate`, `upgrade head`, `downgrade`

**What it is**:

- `alembic init alembic` = create migration system
- `alembic revision --autogenerate -m "reason"` = create new migration (auto-detects schema changes)
- `alembic upgrade head` = apply all pending migrations
- `alembic downgrade -1` = roll back one migration

**Example**:

```bash
# Create migration after adding Column to model
alembic revision --autogenerate -m "add processed_at column to records"

# This creates: alembic/versions/20260402_123456_abc123_add_processed_at.py
# Run one of two ways:
# 1. Inside Docker (uses db:5432 from compose)
docker compose run --rm app uv run alembic upgrade head

# 2. Locally (override DATABASE_URL)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline \
  uv run alembic upgrade head

# Rollback
alembic downgrade -1
```

**[gotcha]**: Never run `Base.metadata.create_all()` alongside migrations. Pick one system (Alembic is production-correct).

---

## Middle Tier (🟡)

### Query Optimization

#### `EXPLAIN ANALYZE` — Read: Actual vs Estimated Rows, Cost, Filter Rows

**What it is**:

- `EXPLAIN ANALYZE SELECT ...` = show query plan + actual execution stats
- Cost = arbitrary units (lower = faster)
- Filter = how many rows survived WHERE clause

**When to use**:

- Query feels slow? Run EXPLAIN ANALYZE to see why
- Did your index help? EXPLAIN shows Seq Scan vs Index Scan

**Example**:

```sql
EXPLAIN ANALYZE
SELECT r.id, r.source, COUNT(r.id) as cnt
FROM records r
WHERE r.processed = false
GROUP BY r.id, r.source
ORDER BY cnt DESC
LIMIT 10;

-- Output:
-- Seq Scan on records r  (cost=0.00..1000.00 rows=10000)
--   Filter: (processed = false)
--   Planning Time: 0.1 ms
--   Execution Time: 50.2 ms

-- ^ "Seq Scan" = bad (scanning all 10K rows)
-- ^ 50ms = slow, add index to help DB

-- After adding index:
CREATE INDEX idx_records_processed_false
  ON records(id, source)
  WHERE processed = false;

-- ^ This makes query faster by only scanning records where processed=false
```

**[gotcha]**: Estimated rows ≠ actual rows. If huge difference, update table statistics: `ANALYZE records;`

---

#### Partial Index: `WHERE processed = false` — Only Index Active Rows

**What it is**:

- `CREATE INDEX idx_name ON table(col) WHERE condition`
- Index only covers rows matching WHERE
- Smaller index = faster queries + less disk space

**When to use**:

- Soft deletes: index only non-deleted rows
- Status flags: index only "active" records

**Example**:

```sql
-- Bad: index all 1M records (includes 900K deleted)
CREATE INDEX idx_records_id ON records(id);

-- Good: index only active 100K records
CREATE INDEX idx_records_active ON records(id)
  WHERE deleted_at IS NULL;

-- In your query:
SELECT * FROM records WHERE id = 123 AND deleted_at IS NULL;
-- ^ uses partial index (fast)
```

---

#### N+1 Detection: Enable `DB_ECHO=True`, Count Queries per Endpoint

**What it is**:

- N+1 = 1 initial query + N "child" queries in a loop
- Example: fetch 100 users (1 query) + fetch each user's profile (100 queries) = 101 total

**When to use**:

- Whenever you suspect "loop + query" pattern

**Example**:

```python
# app/config.py
DB_ECHO = True  # Log every SQL statement

# Run your endpoint
# Terminal shows:
# SELECT id, name FROM users LIMIT 100  -- 1 query
# SELECT * FROM profiles WHERE user_id = 1  -- ✅ N+1 anti-pattern!
# SELECT * FROM profiles WHERE user_id = 2
# ...
# SELECT * FROM profiles WHERE user_id = 100

# Fix: use JOIN or bulk fetch
async def list_users_with_profiles(db: AsyncSession) -> list[dict]:
    """Fetch all users + profiles efficiently."""
    # Bad: 1 + N queries
    users = await db.scalars(select(User))
    for user in users:
        user.profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    
    # Good: 1 query with JOIN
    stmt = (
        select(User)
        .outerjoin(Profile)
        .options(selectinload(User.profile))
    )
    return await db.scalars(stmt).all()
```

---

### PostgreSQL Advanced

#### Connection Pooling: `pool_size`, `max_overflow`, `pool_pre_ping=True`

**What it is**:

- `pool_size` = permanent connections (always open)
- `max_overflow` = temporary connections (exceed size, then close)
- `pool_pre_ping` = test connection before using (prevents stale connections)

**Formula**: `(PostgreSQL max_connections / number_of_app_instances)`

**Example**:

```python
# PostgreSQL max_connections = 100
# You have 5 app instances
# Each instance should use: 100 / 5 = 20 connections

from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=15,           # Always keep 15 open
    max_overflow=5,         # Allow up to 5 temp
    pool_pre_ping=True,     # Test before use
)
# Total: up to 20 connections per instance
# 5 instances × 20 = 100 (exactly at limit)
```

**[gotcha]**: Without `pool_pre_ping`, stale connections cause "connection reset by peer" errors.

---

#### Transactions: Isolation Levels, `SELECT FOR UPDATE`

**What it is**:

- `SELECT FOR UPDATE` = row lock (prevent concurrent updates)
- Isolation levels = balance between consistency + performance

**When to use**:

- `SELECT FOR UPDATE`: concurrent increment (balance += 10), balance -= 5)

**Example**:

```python
async def transfer_balance(
    db: AsyncSession,
    from_user_id: int,
    to_user_id: int,
    amount: float,
) -> None:
    """Transfer money safely."""
    # Lock both rows to prevent concurrent modifications
    from_stmt = (
        select(Account)
        .where(Account.user_id == from_user_id)
        .with_for_update()  # SELECT ... FOR UPDATE
    )
    from_account = await db.scalar(from_stmt)
    
    to_stmt = (
        select(Account)
        .where(Account.user_id == to_user_id)
        .with_for_update()
    )
    to_account = await db.scalar(to_stmt)
    
    # Safe to modify (no one else can modify these rows)
    from_account.balance -= amount
    to_account.balance += amount
    
    await db.commit()
```

---

#### MVCC: Why SELECT Doesn't Block UPDATE; What Causes Table Bloat

**What it is**:

- MVCC = Multi-Version Concurrency Control
- Every UPDATE creates new row version (not in-place modification)
- SELECT sees old version until new transaction commits
- Table bloat = old versions pile up, DB gets slower

**When to use**:

- Understand why long-running queries slow down whole system
- Know when to VACUUM

**Example**:

```
Time: 10:00
- User A: SELECT COUNT(*) FROM huge_table  (starts here)
- User B: UPDATE huge_table SET processed = true  (creates new versions)

Time: 10:05
- User A: still reading (might return wrong count if old versions deleted!)
- User B: committed, new versions are "final"
- PostgreSQL can't delete old versions yet (User A still reading)

Solution: VACUUM manually or configure autovacuum
```

**[gotcha]**: Long-running batch jobs can prevent VACUUM, causing table bloat. Kill them with `SELECT pg_terminate_backend(pid);`

---

#### JSONB Column: `@>`, `?`, `->>` Operators; GIN Index

**What it is**:

- `data @> '{"key": "value"}'` = JSONB contains (very fast with GIN)
- `data -> 'key'` = get field (returns JSONB)
- `data ->> 'key'` = get field as text
- GIN index = makes JSONB searches fast

**Example**:

```python
class Record(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str]
    data: Mapped[dict] = mapped_column(type_=JSON)
    __table_args__ = (
        Index("ix_records_data_gin", data, postgresql_using="gin"),
    )

# Query: find records where data.price > 100
async def find_expensive(db: AsyncSession) -> list[Record]:
    # Without index: slow (scans all rows, parses JSON)
    # With GIN: fast (index on data structure)
    stmt = select(Record).where(
        cast(Record.data["price"].astext, Integer) > 100
    )
    return await db.scalars(stmt).all()
```

---

## Senior Differentiators (🔴)

### Row-Level Security (RLS) for Multi-Tenancy

**What it is**:

- PostgreSQL enforces row-level access policies
- `ALTER TABLE ... ENABLE RLS`
- Each row has a `tenant_id`; users only see their tenant's rows

**When to use**:

- SaaS with multiple customers (prevent data leakage)

---

### `pgvector` Extension for Embedding Storage (AI Pivot)

**What it is**:

- PostgreSQL extension for vector search (AI embeddings)
- `<->` operator = cosine distance (fast with IVFFLAT index)

**When to use**:

- RAG pipelines (store + search embeddings)

---

### Read Replica Routing

**What it is**:

- Direct writes to primary, reads to replica(s)
- Reduces load on primary, enables scaling reads

---

## You Should Be Able To

✅ Write SQL JOINs, GROUP BY, window functions from memory  
✅ Read EXPLAIN ANALYZE output and identify slow queries  
✅ Create appropriate indexes (B-tree, partial, composite)  
✅ Explain MVCC + why SELECT doesn't block UPDATE  
✅ Create/run/roll back Alembic migrations  
✅ Debug "too many connections" errors  
✅ Use `SELECT FOR UPDATE` for concurrent updates  
✅ Design soft-delete columns with partial indexes  
✅ Spot N+1 queries and fix with JOINs  

---

## References

- [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/current/sql-explain.html)
- [SQLAlchemy 2.0 ORM](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [MVCC Explained](https://www.postgresql.org/docs/current/mvcc-intro.html)
