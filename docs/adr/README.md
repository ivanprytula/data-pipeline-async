# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records documenting key design choices across all phases of the data-pipeline-async project.

## What is an ADR?

An ADR captures a significant architectural decision along with:

- **Context** — Why we needed to make this decision
- **Decision** — What we decided (and why)
- **Consequences** — Positive and negative outcomes
- **Alternatives** — Options we considered but rejected

ADRs are not "we built it this way" documentation. They're "we **decided** to build it this way, and here's why" documentation. This preserves reasoning for future maintainers.

---

## ADRs by Phase

### Phase 1–3: Monolith & Scalability

- **ADR 003**: [HTMX vs React](003-htmx-vs-react.md) — Frontend framework decision

### Phase 7: Cloud Deployment & Infrastructure as Code

- **ADR 004**: [ECS Fargate vs EKS](004-ecs-fargate-vs-eks.md) — Container orchestration
  - **Key decision**: Fargate over EKS for simplicity and cost at 5 services scale
  - **Cost impact**: 70% cheaper with Spot instances; simple CI/CD
  - **Trade-off**: Less flexible scheduling; migration path exists if we scale

- **ADR 005**: [GitHub OIDC vs Long-Lived Keys](005-github-oidc-vs-long-lived-keys.md) — CI/CD authentication
  - **Key decision**: Workload identity federation for zero credential rotation
  - **Security impact**: 5-minute token window vs lifetime key exposure
  - **Benefits**: Full CloudTrail audit trail; scalable across repos

- **ADR 006**: [Terraform S3 Backend vs Local State](006-terraform-s3-backend-vs-local.md) — Infrastructure state management
  - **Key decision**: Remote S3 backend with DynamoDB locking for team collaboration
  - **Safety impact**: Prevents concurrent `terraform apply` conflicts
  - **Cost**: ~$0.50/month for S3 + DynamoDB; invaluable for team environments

- **ADR 007**: [Migration Runner vs Sidecar](007-migration-runner-vs-sidecar.md) — Migration execution model for Phase 7 rollout
  - **Status**: Proposed
  - **Focus**: One-shot pre-rollout migration task versus sidecar-triggered migrations
  - **Policy fit**: Keeps Alembic execution out of app startup and preserves blocking deploy gates

---

## Decision Timeline

```
Phase 1–3  → ADR 003 (HTMX)
Phase 7    → ADRs 004, 005, 006, 007 (ECS, OIDC, Terraform, migration execution)
Future     → ADR 008+
```

---

## How to Use ADRs

### For New Features or Changes

1. **Check existing ADRs** — Is there a related decision already documented?
2. **If your change contradicts an ADR** — Either:
   - Document why the ADR is no longer valid (update it), or

- Propose a new superseding ADR (e.g., "ADR 008: Migrate from ECS to EKS")

3. **When in doubt** — Write an ADR before implementing

### For Onboarding

- Read ADRs in phase order (e.g., Phase 7 -> read ADRs 004, 005, 006, 007)
- Understand the "why" behind major decisions
- Use ADRs as teaching material for architectural reasoning

### For Code Reviews

- Reference ADRs when reviewing large architectural changes
- If a PR violates an ADR, ask the author to justify it (and update the ADR if needed)

---

## ADR Status Meanings

| Status | Meaning | Example |
|--------|---------|---------|
| **Proposed** | Suggested but not approved | Not used yet (future) |
| **Accepted** | Approved and implemented | ADRs 003–006 |
| **Deprecated** | Was good; no longer applies | None yet |
| **Superseded** | Replaced by newer ADR | None yet (e.g., if we migrate to EKS) |

---

## Related Documentation

- [Design Decisions](../design/decisions.md) — Quick reference table of all architectural decisions
- [Architecture Overview](../design/architecture.md) — System diagram and Phase Progression
- [Cloud Deployment Guide](../cloud-deployment.md) — Step-by-step setup instructions
- [Portfolio Item: Phase 7](../progress/portfolio-phase-7-cloud-iac.md) — Interview-ready summary

---

## References

- [ADR Template](https://github.com/adr/adr) — Standard ADR format
- [Lightweight ADRs](https://adr.github.io/) — Best practices for decision documentation
- [Why ADRs Matter](https://www.thoughtworks.com/insights/blog/architecture-decision-records-helpful-way-document-decisions) — ThoughtWorks perspective
