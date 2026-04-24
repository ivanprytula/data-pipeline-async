# Migration Metadata Checklist

Use this checklist in pull requests that include Alembic revisions.

## Scope

Applies to persistent-local and production-like schema changes.

Does not apply to ephemeral-local create_all test/scratch flows.

## Required Metadata Per Migration

- Summary of schema intent and affected objects.
- Expand or contract classification.
- Lock impact estimate (low, medium, high) with rationale.
- Expected runtime estimate and cardinality assumptions.
- Reversibility statement (reversible, partially reversible, irreversible).
- Rollback notes with exact downgrade behavior.
- Backfill strategy if data migration is required.

## Compatibility Contract

- Expand first: add nullable columns, tables, indexes.
- Backfill in controlled batches.
- Contract last: drop or rename only after all services stop reading old shape.

## Pre-Merge Validation

- Alembic upgrade head succeeds on fresh database.
- Downgrade base then upgrade head succeeds in CI.
- Required objects exist after migration:
  - Extensions
  - Views or materialized views
  - Partitions
  - Indexes
- Revision chain is linear and expected.

## Release Preflight

- Current database revision recorded.
- Pending migration count is zero before service rollout.
- Connectivity check to target database passes.
- Backup recency satisfies environment policy.

## Failure Policy

- Migration failure blocks deployment.
- No automatic service rollout on migration failure.
- App rollback first when backward-compatible.
- Database downgrade only for tested reversible revisions.

## References

- .github/prompts/plan-dataZooPlatform.prompt.md
- .github/workflows/ci.yml
- docs/design/decisions.md
- docs/dev/gotchas.md
