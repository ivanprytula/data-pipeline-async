# ADR 003: Frontend Strategy — HTMX vs React

**Status**: Accepted
**Date**: April 18, 2026
**Part of**: [Architecture — Data Zoo Platform](../architecture.md)
**Related ADRs**: [ADR 001: Kafka vs RabbitMQ](001-kafka-vs-rabbitmq.md) | [ADR 002: Qdrant vs pgvector](002-qdrant-vs-pgvector.md)
**Context**: Phase 6 requires a dashboard UI for browsing records, semantic search, and live metrics. Frontend choice has learning implications.

---

## Decision

**Use HTMX + Jinja2 templates for backend-rendered HTML. No JavaScript framework.**

---

## Options Considered

### Option A: HTMX + Jinja2 (Backend-rendered HTML)

- **Pros:**
  - Stay in Python (single language for entire project)
  - Simpler mental model (HTML is HTML, not JSX)
  - No SPA complexity (no bundler, no state management library)
  - Server-side rendering is more accessible (works without JavaScript)
  - HTMX adds interactivity (AJAX requests for specific UI updates) without JavaScript framework
  - Minimal learning curve
- **Cons:**
  - Less responsive feel than SPA (page reloads not instant)
  - Can't work offline
  - Network requests on every interaction (higher latency for some interactions)
  - UI state lives on server (requires session management)

### Option B: React (SPA)

- **Pros:**
  - Highly responsive; instant UI updates
  - Rich ecosystem (routing, state management, component libraries)
  - Works offline (with service workers)
  - Separates frontend and backend completely
  - Better for complex interactive UIs
- **Cons:**
  - Separate tech stack (Node.js, npm, webpack, Babel)
  - Larger learning curve (JSX, state management, hooks)
  - More boilerplate
  - Requires backend API changes to support SPA patterns
  - Deployment complexity (build → bundle → upload)

### Option C: Vue.js

- **Pros:**
  - Lighter than React
  - Single-file components
  - Progressive enhancement (can build pieces incrementally)
- **Cons:**
  - Still a separate JavaScript ecosystem
  - Smaller community than React
  - Doesn't align with "stay in Python" goal

---

## Rationale

**Chosen: HTMX + Jinja2**

1. **Goal Alignment**: Data Zoo is a Python/backend learning platform, not a frontend benchmarking project. HTMX keeps you in Python.
2. **Learning Value**: HTMX teaches you AJAX / dynamic HTML principles without the React abstraction layer. You learn HTTP semantics first.
3. **Operational Simplicity**: No build step, no Node.js, no npm. Just Python `+ jinja2`.
4. **Accessibility**: Server-rendered HTML is more accessible by default (screen readers, search engines, low-bandwidth users).
5. **Realistic**: Many backend teams use templates + HTMX (not every company uses React).

---

## Consequences

### Positive

- Single technology stack (Python → HTML → HTMX)
- Fast iteration (no build pipeline)
- Server-side rendering scales better for many concurrent users
- Learning focus stays on backend, not frontend framework philosophy

### Negative

- Dashboard is less snappy than React SPA
- No offline capability
- UI state on server requires careful session management
- Limited to browser capabilities (no mobile app)

---

## Implementation

**Phase 6**: Create dashboard service

```python
# services/dashboard/main.py
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    records = await crud.get_records(db, skip=0, limit=100)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "records": records
    })
```

```html
<!-- templates/index.html -->
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/htmx.org@1.9.5"></script>
</head>
<body>
    <div hx-get="/records?page=1" hx-trigger="load" hx-target="this">Loading...</div>
</body>
</html>
```

**Features:**

- Records explorer: HTMX infinite scroll (hx-trigger="revealed")
- Semantic search: Form posts to backend, returns partial HTML
- Metrics: Server-Sent Events (SSE) stream Prometheus counters

---

## Alternatives Reconsidered

**React instead**: Would be valid for a frontend-heavy project, but Data Zoo is backend-focused. React would distract from core learning (event streaming, AI, database optimization).

**Vue.js instead**: Lighter than React, but still requires Node.js ecosystem. HTMX gives you the same interactivity with zero extra dependencies.

---

## Review Notes

- HTMX is modern (2023+), not retro
- Performance: HTMX requests are ~50-100ms (acceptable for dashboard)
- If needed later, you could migrate to React (API would already be RESTful)
- Interview question: "When would you choose a backend template engine vs a SPA?"
