## Plan: Production Alembic Strategy Split

Define and document a strict migration model: Alembic is authoritative for CI/staging/prod and local persistent databases, while schema-creation-only (`create_all`) is allowed only in explicitly ephemeral local modes (tests/scratch DBs). Expand the roadmap prompt by replacing the current scope-excluded bullet with a concise, enforceable strategy section tied to deployment phases.

**Steps**
1. Baseline and terminology lock
- Capture one source-of-truth policy statement for three environments: `ephemeral-local`, `persistent-local`, and `production-like`.
- Define prohibited pattern explicitly: do not run Alembic from FastAPI lifespan/event loop; do not mix `create_all` and Alembic on the same persistent database.
- Depends on: none.

2. Add strategy section in roadmap prompt (*depends on 1*)
- In `.github/prompts/plan-dataZooPlatform.prompt.md`, replace the single scope-excluded bullet with a dedicated subsection named for migration strategy.
- Include: ownership, execution point, rollback model, safety gates, and local-ephemeral exception.
- Keep this section concise (roadmap level), with pointers to existing docs for deep details.

3. Define runtime execution model by deployment stage (*depends on 2*)
- Pre-Phase/Phase 0: keep local bootstrap using Alembic (`upgrade head`) for persistent local DB.
- Phase 7 (ECS rollout): introduce one-shot migration runner before service rollout (separate task/job, never app startup).
- Production deploy sequence: build image -> run migrations once -> verify schema revision -> roll services.
- Rollback sequence: app rollback first if backward-compatible; DB downgrade only for tested reversible revisions.

4. Define migration authoring rules and compatibility contract (*depends on 2, parallel with 3*)
- Expand/contract policy for zero-downtime:
- Expand: add nullable columns/tables/indexes concurrently where applicable.
- Migrate data in backfill jobs/batches.
- Contract: drop/rename only after all services stop reading old shape.
- Require every migration to include risk notes: lock impact, expected runtime, reversibility.

5. Add CI/CD governance requirements (*depends on 3 and 4*)
- Keep migration job as blocking gate before integration/e2e and release promotion.
- Add drift check policy: DB at `head` before deploy.
- Add preflight checks in release pipeline: current revision, pending migrations count, DB connectivity, backup recency.
- Define fail behavior: migration failure blocks deploy; no automatic app rollout.

6. Local schema-creation-only policy (*depends on 1*)
- Explicitly scope `create_all` to ephemeral contexts only (tests, temporary scratch DB profile).
- For persistent local databases, mandate Alembic to avoid drift from CI/prod.
- Add guardrail recommendation: startup warning/error if `create_all` is attempted against non-ephemeral profiles.

7. Verification and runbook alignment (*depends on 5 and 6*)
- Add validation checklist in prompt strategy section:
- Fresh DB: `upgrade head` succeeds.
- Idempotency path: `downgrade base` then `upgrade head` succeeds in CI.
- Object checks: extensions/views/partitions/indexes present.
- Deployment dry run: migration runner exits cleanly before service rollout.

8. Scope boundaries and future integration (*depends on 2-7*)
- Keep deep operational details in existing docs (`docs/design/*`, `docs/dev/*`, workflow docs).
- Keep prompt focused on roadmap policy and phase handoff criteria.
- Out-of-scope for this plan: implementing migration runner code, editing CI workflows, writing new Terraform resources.

**Relevant files**
- `/home/ivanp/PersonalProjects/data-pipeline-async/.github/prompts/plan-dataZooPlatform.prompt.md` — replace scope-excluded Alembic bullet with enforceable migration strategy subsection.
- `/home/ivanp/PersonalProjects/data-pipeline-async/.github/workflows/ci.yml` — reference as existing migration gate pattern to preserve.
- `/home/ivanp/PersonalProjects/data-pipeline-async/alembic/env.py` — reference for current authoritative Alembic configuration behavior.
- `/home/ivanp/PersonalProjects/data-pipeline-async/scripts/setup/01-bootstrap-dev-environment.sh` — reference for persistent-local bootstrap (`alembic upgrade head`).
- `/home/ivanp/PersonalProjects/data-pipeline-async/docs/dev/gotchas.md` — reference for Python 3.14 rule: avoid invoking Alembic from app event loop.
- `/home/ivanp/PersonalProjects/data-pipeline-async/docs/design/decisions.md` — reference for Alembic vs `create_all` decision framing.

**Verification**
1. Roadmap prompt contains a migration strategy subsection with explicit environment split and no contradictory “out-of-scope” wording for production migrations.
2. Strategy text explicitly states: Alembic for persistent/local+prod-like, `create_all` only for ephemeral local mode.
3. Strategy text includes deployment ordering and failure behavior (migration failure blocks rollout).
4. Strategy text includes rollback policy and expand/contract compatibility requirements.
5. Strategy text links back to existing docs/workflows rather than duplicating low-level procedures.

**Decisions**
- Confirmed: local default remains Alembic; `create_all` is only for ephemeral mode.
- Confirmed: strategy should be expanded directly in `.github/prompts/plan-dataZooPlatform.prompt.md` (replace current excluded bullet).
- Included scope: planning/document-structure and policy definition.
- Excluded scope: implementing code/workflow/infra changes.

**Further Considerations**
1. Recommendation: add an ADR for migration execution in cloud deploys (one-shot runner vs sidecar) when Phase 7 implementation starts.
2. Recommendation: add a “long-running migration playbook” later (timeouts, chunked backfills, lock windows) if table volume grows.
3. Recommendation: standardize migration metadata template (risk, lock type, rollback notes) in PR checklist.
