# ADR-003: HTMX vs React for the Dashboard

**Status:** Accepted
**Date:** 2026-04-21
**Context:** Phase 6 — Data Zoo dashboard UI

---

## Context

The Data Zoo platform needs a monitoring and data-exploration dashboard with three views:

1. **Records Explorer** — paginated table with filtering and infinite scroll
2. **Semantic Search** — form-driven search against the AI gateway
3. **Live Metrics** — real-time counters streamed from the ingestor

The dashboard is a *learning tool* attached to a backend-focused project. It will be maintained by one person and must stay simple enough to reason about without frontend build tooling.

---

## Decision

Use **HTMX + Jinja2** served by a FastAPI service (`services/dashboard/`). No JavaScript framework (React, Vue, Svelte).

---

## Considered Options

| Criterion | HTMX + Jinja2 | React (SPA) |
|-----------|--------------|-------------|
| **Build tooling** | None | Node, Vite/CRA, Babel, bundler |
| **Bundle size** | ~14 KB (htmx.min.js) | 40–150 KB min (React + ReactDOM) |
| **Interactivity model** | HTML-over-the-wire: server renders fragments | JSON-over-the-wire: client renders from state |
| **SSE integration** | First-class via `hx-ext="sse"` | Requires `EventSource` wiring + state management |
| **Infinite scroll** | `hx-trigger="revealed"` — one HTML attribute | Intersection Observer + fetch + state reconciliation |
| **Learning surface** | Deepens Python/Jinja2; minimal new domain | Large JS ecosystem (hooks, bundling, deployment) |
| **Operational complexity** | Single Python process | Separate frontend build, CDN deploy, CORS config |
| **Type safety** | Jinja2 is untyped; runtime errors | Full TypeScript support available |
| **Component reuse** | Jinja2 macros + `{% include %}` partials | React components — excellent reuse |
| **Real-time UX** | Adequate for metrics dashboard | Smoother transitions and local state |

---

## Rationale

### Why HTMX wins here

1. **Complexity budget.** This is a 16-week learning platform. Every hour spent debugging Webpack/Vite configs or managing React state is an hour *not* spent on the distributed systems topics the project is designed to teach.

2. **Operational simplicity.** The dashboard is a single FastAPI service with no build step. The same `Dockerfile` pattern used by every other service applies — no separate CDN, no CORS config, no frontend pipeline.

3. **SSE is trivial.** The `hx-ext="sse"` attribute handles reconnection, event dispatch, and DOM swapping in one line of HTML. In React, the same feature requires `EventSource`, `useEffect`, `useState`, cleanup on unmount, and error boundary logic.

4. **Infinite scroll with one attribute.** `hx-trigger="revealed"` on the last table row triggers the next page load automatically. The server returns `<tr>` fragments — no client-side pagination state.

5. **Backend-aligned.** The rendered HTML is produced by Jinja2 on the server, colocated with the Python code. Template bugs are debugged with the same tools as API bugs. There is no context switch between languages.

### When React would be the right choice

- The UI requires complex local state (drag-and-drop, multi-step wizards, optimistic updates).
- Multiple teams own the frontend vs backend, requiring a clean API contract.
- Mobile app parity is needed (React Native).
- The frontend is a product in itself, not an operational dashboard.

None of these apply here.

---

## Consequences

### Positive

- Zero Node.js toolchain required; `docker compose up` works immediately.
- Dashboard templates live in `services/dashboard/templates/` alongside the Python code.
- Dashboard pages split cleanly into `services/dashboard/routers/pages.py` and `services/dashboard/routers/sse.py`, keeping the three browser views small and explicit.
- SSE endpoint (`/sse/metrics`) tested and consumed without a JS framework.
- CSS bundle is hand-written (~250 lines) — no Tailwind JIT compilation needed.

### Negative / Trade-offs accepted

- Jinja2 templates are not type-checked; template variable mismatches fail at runtime.
- Rich client-side interactions (animated transitions, offline support) are harder.
- If the dashboard ever needs to become a product, a migration to React would be substantial.

---

## Implementation

```text
services/dashboard/
├── main.py                        FastAPI app, static file mount
├── constants.py                   DEFAULT_PAGE_SIZE, service URLs
├── routers/
│   ├── pages.py                   Full-page routes + HTMX partials
│   └── sse.py                     /sse/metrics — Prometheus text scraper → SSE
├── templates/
│   ├── base.html                  nav, static assets
│   ├── index.html                 Records Explorer (infinite scroll)
│   ├── search.html                Semantic Search (hx-post form)
│   ├── metrics.html               Live Metrics (hx-ext="sse")
│   └── partials/
│       ├── records_rows.html      <tbody> fragment (infinite scroll target)
│       └── search_results.html    <ul> fragment (search results target)
└── static/
    ├── htmx.min.js                vendored HTMX 1.9.x
    ├── htmx-sse.js                vendored HTMX SSE extension
    └── style.css                  hand-written CSS (~250 lines)
```

Key HTMX patterns used:

```html
<!-- Infinite scroll: last row triggers next page when it enters the viewport -->
<tr hx-get="/partials/records?skip=50"
    hx-trigger="revealed"
    hx-target="closest table tbody"
    hx-swap="beforeend">

<!-- SSE: connects on mount, swaps innerHTML on each "message" event -->
<div hx-ext="sse" sse-connect="/sse/metrics" sse-swap="message">

<!-- Form: submits, shows spinner, replaces results div -->
<form hx-post="/partials/search"
      hx-target="#search-results"
      hx-indicator="#search-spinner">
```

---

## References

- [HTMX documentation](https://htmx.org/docs/)
- [Hypermedia Systems (book)](https://hypermedia.systems/)
- [ADR-001: Kafka vs RabbitMQ](../design/adr/001-kafka-vs-rabbitmq.md)
- [ADR-002: Qdrant vs pgvector](../design/adr/002-qdrant-vs-pgvector.md)
