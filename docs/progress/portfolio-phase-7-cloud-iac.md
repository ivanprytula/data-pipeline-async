# Portfolio Item: Phase 7 — Cloud Deployment & Infrastructure as Code

**Status**: ✅ Complete
**Timeline**: Week 13–14 (April 2026)
**Core Question**: "Walk me through your multi-environment infrastructure deployment (dev/prod). What trade-offs did you make?"

---

## Problem Statement

Data Zoo runs perfectly on `docker-compose` locally. Now it needs to run on AWS with:

1. **Multi-environment strategy** — dev (cheap, Spot), prod (reliable, on-demand)
2. **Zero-downtime deployments** — rolling updates with health checks
3. **Infrastructure as code** — reproducible, team-safe, versionable
4. **Security by default** — no AWS keys in git, OIDC auth, encrypted data at rest
5. **Cost optimization** — 70% cheaper in dev without sacrificing reliability in prod

---

## Solution: ECS Fargate + Terraform on AWS

### Architecture Decision

Why ECS Fargate (not EKS)?

| Factor             | ECS Fargate                       | EKS                          | Trade-off                            |
| ------------------ | --------------------------------- | ---------------------------- | ------------------------------------ |
| **Ops burden**     | None (managed)                    | High (nodes, upgrades, CNI)  | Pay $ for simplicity                 |
| **Learning curve** | 2 hours (ALB, IAM, ECS)           | 2 weeks (K8s API, CRDs)      | Fargate focuses on patterns, not ops |
| **Cost (dev)**     | ~$85/month                        | ~$100+/month                 | Fargate cheaper + Spot = 70% savings |
| **CI/CD**          | `aws ecs update-service` (1 call) | `kubectl set image` + GitOps | Fargate is simpler                   |
| **Suitable for**   | 1–10 services                     | 50+ services, platform team  | This project is 5 services           |

**Decision**: Kubernetes is a separate dedicated learning project. Fargate lets us focus on distributed systems patterns (service-to-service communication, resilience, observability) without the distraction of cluster administration.

---

## Deliverables

### 1. Terraform Infrastructure Modules (7 modules, ~20 files)

**Location**: `infra/terraform/modules/`

| Module       | Responsibility                          | Key Resources                                                                                 |
| ------------ | --------------------------------------- | --------------------------------------------------------------------------------------------- |
| `network/`   | VPC, subnets, IGW, NAT, security groups | 2 public + 2 private subnets (2 AZs), 5 security groups (least-privilege)                     |
| `ecr/`       | Container registry                      | ECR repos for all 5 services                                                                  |
| `iam/`       | GitHub Actions OIDC provider            | No long-lived AWS keys in CI/CD; trust policy scoped to main/develop branches                 |
| `database/`  | RDS PostgreSQL 17                       | gp3 encrypted storage, managed password (Secrets Manager), Multi-AZ toggle                    |
| `cache/`     | ElastiCache Redis 7.1                   | TLS in-transit, AUTH token, automatic failover (prod)                                         |
| `messaging/` | MSK Serverless (Kafka)                  | IAM auth (no passwords), private subnets                                                      |
| `compute/`   | ECS cluster, ALB, task definitions      | ALB with HTTPS listener, ingestor + 4 service task defs, circuit breaker for safe deployments |

### 2. Environment Configurations (dev/prod)

**Location**: `infra/terraform/environments/dev/` and `environments/prod/`

**dev (cost-optimized)**:

- Fargate Spot (saves 70% on compute)
- db.t3.micro (512 MB RAM, suitable for ~100 concurrent connections)
- 1 NAT Gateway (shared)
- 14-day backup retention
- Cost: ~$85/month

**prod (reliability-focused)**:

- Fargate On-Demand (guaranteed capacity)
- db.t3.medium Multi-AZ (high availability, automatic failover)
- 3 NAT Gateways (one per AZ, no single point of failure)
- 90-day backup retention
- Cost: ~$280/month

### 3. CI/CD Integration

**Workflows**:

- `.github/workflows/ci.yml`
- `.github/workflows/docker-build.yml`
- `.github/workflows/release-promote.yml`
- `.github/workflows/cd-deploy.yml`

```text
Commit / PR
  ↓
Queued CI workflow
  Quality → Unit → Migrations → Integration → E2E
  PR-only dependency audit
  Push-only image build validation for all 5 services
  ↓
Manual Docker build workflow
  - select one service or all services
  - optional ECR push
  - optional signing
  ↓
Manual release promotion workflow
  - promote one service or all services by digest/tag
  ↓
Manual CD deploy workflow
  - select environment + service
  - deploy to ECS via environment-specific variables
```

**Key innovation**: GitHub OIDC provider replaces long-lived AWS access keys

- GitHub generates JWT per workflow run
- Service exchanges JWT for temporary AWS credentials
- Credentials scoped to ECR push only
- CloudTrail audit trail of all role assumptions
- No credential rotation burden

### 4. Comprehensive Documentation

**Main guide**: [docs/cloud-deployment.md](../cloud-deployment.md)

Covers:

- Why ECS Fargate (with cost/ops comparison table)
- First-time setup (AWS profiles, S3 backend, GitHub secrets)
- Terraform module structure and parameterization
- Secrets management strategy (Secrets Manager vs SSM Parameter Store)
- Manual deployment commands
- Manual build / promote / deploy workflow model
- Cost breakdown and teardown procedures

**Architecture doc**: [docs/design/architecture.md](../design/architecture.md)

Covers:

- Phase 7 section with infrastructure diagram
- Terraform module patterns and reusability
- CI/CD workflow flow chart
- Deployment flow and health checks
- Design patterns (IaC, secrets management, resilience, cost optimization)

**Decision document**: [docs/design/decisions.md](../design/decisions.md)

Added Phase 7 decision entries:

- ECS Fargate vs EKS trade-off analysis
- RDS PostgreSQL vs Aurora vs DocumentDB
- ElastiCache Redis vs Memcached vs DynamoDB
- MSK Serverless vs self-managed Kafka
- S3 backend + DynamoDB state locking (team-safe Terraform)
- GitHub OIDC vs long-lived access keys (security best practice)
- dev/prod environment strategy (cost optimization without sacrificing reliability)

---

## Technical Deep Dive

### Terraform Patterns

**Module reusability**: All modules parameterized via `variables.tf`

```hcl
# Example: database module accepts parameters
module "database" {
  source = "../modules/database"

  allocated_storage       = var.db_allocated_storage      # 20 GB (dev) or 100 GB (prod)
  instance_class          = var.db_instance_class         # t3.micro (dev) or t3.medium (prod)
  multi_az                = var.db_multi_az               # false (dev) or true (prod)
  backup_retention_days   = var.backup_retention_days     # 7 (dev) or 14 (prod)
}
```

**No hardcoded values** — all in `terraform.tfvars`:

```hcl
# Dev example
vpc_cidr                = "10.0.0.0/16"
db_instance_class       = "db.t3.micro"
fargate_launch_type     = "FARGATE_SPOT"
nat_gateway_count       = 1
backup_retention_days   = 14
```

**State management**: Remote S3 backend with DynamoDB locking

```hcl
# Prevents concurrent applies, stores version history
backend "s3" {
  bucket         = "data-zoo-terraform-state-dev"
  key            = "data-zoo/dev/terraform.tfstate"
  region         = "eu-central-1"
  dynamodb_table = "data-zoo-terraform-locks"
  encrypt        = true
}
```

### Secrets Management Strategy

**Never in code or state files**:

- Sensitive values passed via environment variables: `export TF_VAR_redis_auth_token=$(openssl rand -hex 32)`
- RDS password managed by AWS Secrets Manager (auto-rotated)
- ElastiCache AUTH token stored in SSM Parameter Store

**ECS task definitions**: All secrets injected at runtime

```json
{
  "secrets": [
    {
      "name": "DATABASE_PASSWORD",
      "valueFrom": "arn:aws:secretsmanager:eu-central-1:123456:secret:data-zoo/rds-password"
    },
    {
      "name": "REDIS_AUTH_TOKEN",
      "valueFrom": "arn:aws:ssm:eu-central-1:123456:parameter:/data-zoo/dev/redis-token"
    }
  ]
}
```

Never visible in CloudWatch logs or Terraform state.

### Resilience Patterns

**ALB health checks** (5s interval, 3 consecutive failures to mark unhealthy)

```hcl
health_check {
  path             = "/health"
  matcher          = "200"
  interval         = 5
  timeout          = 3
  healthy_threshold   = 2
  unhealthy_threshold = 3
}
```

**ECS circuit breaker** (stops rollout if too many tasks fail to reach running)

```hcl
deployment_circuit_breaker {
  enable   = true
  rollback = true  # Auto-rollback on failure
}
```

**Rolling update policy** (zero-downtime deployments)

```hcl
deployment_configuration {
  minimum_healthy_percent = 100  # Keep all healthy
  maximum_percent         = 200  # Allow 2x replicas during update
}
```

---

## Cost Analysis

### Monthly Breakdown (USD)

| Service                   | Dev                  | Prod                      | Rationale                                       |
| ------------------------- | -------------------- | ------------------------- | ----------------------------------------------- |
| **ECS Fargate (compute)** | $15–20 (Spot)        | $50–60 (On-Demand)        | Spot 70% cheaper; prod needs reliability        |
| **RDS PostgreSQL**        | $20 (t3.micro)       | $50 (t3.medium, Multi-AZ) | Prod reads replicate to standby                 |
| **ElastiCache Redis**     | $10 (t3.micro)       | $25 (t3.small)            | Prod runs replica in different AZ               |
| **NAT Gateway**           | $32 (1 GW × 24h)     | $100 (3 GWs × 24h)        | Prod needs HA (egress from each AZ)             |
| **MSK Serverless**        | ~$5 (low throughput) | ~$30 (higher throughput)  | Scales with msg volume                          |
| **CloudWatch Logs**       | ~$3                  | ~$10                      | 14-day (dev) vs 90-day (prod) retention         |
| **Total/month**           | **~$85**             | **~$280**                 | 70% savings in dev via Spot + smaller instances |

**Annual savings**:

- Shared environment (always prod-sized): $280 × 12 = $3,360/year
- Separate dev/prod: ($85 × 12) + ($280 × 12) = $4,380/year
- Break-even: When you have enough deployments that Spot interruptibility costs more than savings

---

## What This Teaches

### Infrastructure as Code (IaC) Principles

1. **Reusability** — modules encapsulate, parameterize, deploy to multiple environments
2. **Repeatability** — `terraform apply` gives same result every time (idempotent)
3. **Auditability** — state stored in git; who changed what and when
4. **Team collaboration** — S3 backend + DynamoDB locks prevent merge conflicts

### AWS Service Selection

1. **Managed services** (RDS, ElastiCache, MSK) trade control for operations
2. **Trade-off reasoning** — lower cost/ops vs higher latency/less customization
3. **Scaling strategy** — Spot for non-critical workloads, On-Demand for SLAs

### Security by Default

1. **No credentials in git** — OIDC provider, environment variables, Secrets Manager
2. **Least privilege** — security groups, IAM policies, readonly task containers
3. **Encryption** — data at rest (RDS gp3, ElastiCache TLS), in transit (HTTPS)

### Cost Optimization

1. **dev/prod split** — different sizing, Spot in dev, HA in prod
2. **Reserved instances** (future) — commit for 1–3 years for 30–40% discount
3. **Monitoring** — CloudWatch metrics to detect wasteful resources

---

## Interview Answers

### "Walk me through your multi-environment infrastructure"

> "I use Terraform with 7 reusable modules (network, RDS, ElastiCache, MSK, IAM, ECR, ECS). Each environment (dev/prod) passes parameters to these modules. Dev runs Fargate Spot instances on db.t3.micro to save 70% cost; prod uses On-Demand with db.t3.medium Multi-AZ for reliability. Terraform state lives in S3 with DynamoDB locking so my team doesn't have conflicts. No AWS keys in GitHub — I use OIDC for CI/CD auth."

### "What's one trade-off you made?"

> "I chose ECS Fargate over EKS. Kubernetes would give me more power and control, but the ops burden — node upgrades, CNI config, CRD management — would distract from learning distributed systems patterns. Fargate lets me focus on service-to-service communication, resilience, observability. If this project scaled to 50+ microservices, I'd reconsider EKS. But for 5 services, Fargate is the pragmatic choice."

### "How do you handle secrets?"

> "All secrets are environment variables or AWS Secrets Manager, never in code or state files. GitHub stores only non-sensitive values (AWS_ACCOUNT_ID). When CI/CD runs, GitHub OIDC exchanges a JWT for temporary AWS credentials. ECS task definitions pull secrets from Secrets Manager at runtime — they're never logged or visible in CloudWatch."

### "How much does this cost?"

> "Dev is $85/month (Fargate Spot + micro DB); prod is $280/month (On-Demand + Medium DB + HA). The 70% dev savings comes from Spot instances and small instance types. If I needed more than 1 NAT Gateway in dev, cost would spike to $150/month — that's why I keep dev simple until it becomes a bottleneck."

---

## Files Created/Modified

| File                                    | Type     | Purpose                                                      |
| --------------------------------------- | -------- | ------------------------------------------------------------ |
| `infra/terraform/main.tf`               | Created  | Provider config, backend template                            |
| `infra/terraform/variables.tf`          | Created  | Shared variables (region, CIDR, instance types)              |
| `infra/terraform/outputs.tf`            | Created  | Exports (ALB DNS, ECR URLs, IAM role ARN)                    |
| `infra/terraform/modules/network/*`     | Created  | VPC, subnets, IGW, NAT, 5 security groups                    |
| `infra/terraform/modules/ecr/*`         | Created  | ECR repositories                                             |
| `infra/terraform/modules/iam/*`         | Created  | GitHub OIDC provider + role                                  |
| `infra/terraform/modules/database/*`    | Created  | RDS PostgreSQL 17                                            |
| `infra/terraform/modules/cache/*`       | Created  | ElastiCache Redis 7.1                                        |
| `infra/terraform/modules/messaging/*`   | Created  | MSK Serverless                                               |
| `infra/terraform/modules/compute/*`     | Created  | ECS cluster, ALB, task definitions                           |
| `infra/terraform/environments/dev/*`    | Created  | Dev environment variables and tfvars example                 |
| `infra/terraform/environments/prod/*`   | Created  | Prod environment variables and tfvars example                |
| `.github/workflows/ci.yml`              | Modified | Queued CI gates plus build validation for all service images |
| `.github/workflows/docker-build.yml`    | Modified | Manual per-service or all-service build, optional push/sign  |
| `.github/workflows/release-promote.yml` | Created  | Manual digest/tag promotion for one service or all services  |
| `.github/workflows/cd-deploy.yml`       | Modified | Manual per-service deploy target resolution                  |
| `docs/cloud-deployment.md`              | Created  | Comprehensive Phase 7 guide (setup, secrets, costs)          |
| `docs/design/architecture.md`           | Modified | Added Phase 7 section with infrastructure diagrams           |
| `docs/design/decisions.md`              | Modified | Added 7 Phase 7 decision entries + matrix                    |
| `README.md`                             | Modified | Updated phase status and docs index                          |

---

## How to Use This

### First-Time Deployment (dev)

```bash
cd infra/terraform/environments/dev
terraform init \
  -backend-config="bucket=data-zoo-terraform-state-dev" \
  -backend-config="key=data-zoo/dev/terraform.tfstate" \
  -backend-config="region=eu-central-1" \
  -backend-config="dynamodb_table=data-zoo-terraform-locks"

cp terraform.tfvars.example terraform.tfvars
# Edit: add your acm_certificate_arn

aws-vault exec data-zoo-dev -- terraform plan
aws-vault exec data-zoo-dev -- terraform apply
```

### Deploying Code Changes

Current deployment model is manual by design:

```bash
gh workflow run docker-build.yml
gh workflow run release-promote.yml
gh workflow run cd-deploy.yml
```

For direct AWS CLI rollout, `aws ecs update-service` still works, but GitHub Actions is now the primary manual delivery path.

### Teardown (when done)

```bash
terraform destroy  # Removes all AWS resources
aws s3 rm s3://data-zoo-terraform-state-dev --recursive  # Clean up state bucket
```

---

## Next Steps (Phase 8)

- Add Prometheus + Grafana for observability
- Implement backup strategy (pg_dump to S3, WAL-G)
- Add chaos engineering tests (kill random tasks, partition network)
- OWASP security audit (rate limiting, input validation, CORS)

---

## References

- [Cloud Deployment Guide](../cloud-deployment.md)
- [Architecture Overview](../design/architecture.md)
- [Infrastructure Decisions](../design/decisions.md)
- [Terraform Module Patterns](../../infra/terraform/modules)
