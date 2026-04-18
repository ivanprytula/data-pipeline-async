# Plan A: Sync/Async Docs Migration

**TL;DR**: Extract the sync/async comparison content from README into `docs/sync-vs-async.md` as an archived reference. Replace the README header with the async-only title + a single backlink.

**Steps**
1. CREATE `docs/sync-vs-async.md` — move these sections verbatim from README:
   - H1 title "Week 1 — Data Pipeline Starter Kit" → new H1 "Sync vs Async — Historical Reference"
   - Intro paragraphs + `week1_data_pipeline/` folder tree
   - "Sync vs Async — What Changes and Why" table (8 rows) + "When to choose" paragraphs
   - "Quick Start — sync" bash block (archive label it)
2. EDIT `README.md` — replace lines 1–60 (everything up to and including `## Quick Start — async`):
   - New H1: `# Data Pipeline — Async`
   - One-liner description
   - Blockquote backlink: `> **Historical reference**: [docs/sync-vs-async.md](docs/sync-vs-async.md)`
   - `---` divider
   - Rename `## Quick Start — async` → `## Quick Start`
3. EDIT `README.md` "Project Structure" code block — change `sync/ (and async/ — identical layout)` to `async/` only

**Relevant files**
- `README.md` — remove lines 1–60 (sync header, table, sync quick start); rename `## Quick Start — async` → `## Quick Start`; fix project structure block
- `docs/sync-vs-async.md` — CREATE with archived content

**Verification**
1. `README.md` opens with `# Data Pipeline — Async` as the only H1
2. `docs/sync-vs-async.md` contains the 8-row sync/async table and sync quick-start commands
3. Backlink in README resolves to the new doc
4. No `markdownlint` violations (`npx markdownlint-cli README.md docs/sync-vs-async.md`)

**Decisions**
- Content is preserved verbatim in `docs/` — no information loss
- Out of scope: modifying any Python source files
