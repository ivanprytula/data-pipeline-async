## Cloud deployment — Safe defaults

This document records recommended safe defaults for continuous deployment (CD) in this repository.

Summary

- CD workflows in this repo are manual by default: see `.github/workflows/cd-deploy.yml` which uses `workflow_dispatch` only.
- Recommended safe defaults: require environment protections for `prod` (and optionally `dev`), store secrets in environment-scoped secrets, and remove stale branch-protection contexts.

Why

- Manual deploys + environment protection reduce blast radius and prevent CI from accidentally triggering production changes.

Recommendations (safe defaults)

1. Keep CD workflows manual

- Do not add `workflow_run` or other automatic triggers to call `cd-deploy.yml` or the reusable `deploy-reusable.yml` unless you explicitly opt in.

1. Protect the `prod` environment (and optionally `dev`)

- In GitHub: Repository → Settings → Environments → Add `prod` (if not present) → Protect environment.
  - Add required reviewers (teams or individuals) to enforce human approvals.
  - Optionally add a `wait timer` to delay deployments.

- UI steps (quick):
  1. Go to <https://github.com/><OWNER>/<REPO>/settings/environments
  2. Click the environment name (e.g., `prod`).
  3. Under "Protection rules" add required reviewers or teams and save.

1. Store deployment secrets as environment-scoped secrets

Use the `gh` CLI to create environment secrets rather than storing values at repo or org level.

Example to set `CI_POSTGRES_PASSWORD` for `prod` (run locally as a repo admin):

```bash
# from a machine with gh CLI authenticated as a repo admin
export CI_POSTGRES_PASSWORD="${CI_POSTGRES_PASSWORD}"  # set locally beforehand
gh secret set CI_POSTGRES_PASSWORD --env prod --body "$CI_POSTGRES_PASSWORD"
```

1. Remove stale 'Expected' branch-protection contexts

This repo contains `scripts/tools/set-branch-protection-gh.sh` which can discover check-run contexts observed on `main` and apply them to branch-protection rules.

Example (requires `gh` + `jq`, and repo admin):

```bash
bash scripts/tools/set-branch-protection-gh.sh --discover --discover-ref main --branches main,develop --apply
```

1. Quick verification and CI run

- Verify the required secret `CI_POSTGRES_PASSWORD` exists in the `prod` environment (or other required secrets used by deployment).
- Trigger a full CI run after protections and secrets are configured:

```bash
# example (adjust fields as needed)
gh workflow run ci.yml --ref main --field run_slow_checks=true --field run_docker_build=false
```

Notes

- Creating environment protections and editing branch-protection requires repository admin permissions.
- The helper script `scripts/tools/apply-github-environment-protection.sh` (in this repo) can set environment secrets from local env vars and points you to the UI for reviewer setup.

If you want, I can prepare the `gh api` payloads to apply environment protection programmatically; this requires team/user IDs and admin privileges.
# Cloud Deployment — ECS Fargate on AWS

## Why ECS Fargate (not EKS)

This project deploys to ECS Fargate. The choice is deliberate:

| Concern              | ECS Fargate                           | EKS                                                     |
| -------------------- | ------------------------------------- | ------------------------------------------------------- |
| Ops overhead         | None — no nodes, no control plane     | Significant — node groups, kube-system addons, upgrades |
| Learning curve       | Low — IAM + ECR + ECS concepts only   | High — Kubernetes API, RBAC, CNI, CRDs                  |
| Cost (dev)           | ~$10–30/month for 1 task              | ~$70/month (control plane) + nodes                      |
| Cost (prod, 2 tasks) | ~$40–60/month                         | ~$150–200/month baseline                                |
| Service mesh         | Not needed at this scale              | Istio/Linkerd adds ~30% overhead                        |
| CI/CD                | `aws ecs update-service` (1 CLI call) | `kubectl set image` + rollout watch                     |
| Suitable for         | 1–10 services, low ops budget         | 10+ services, platform team, GitOps                     |

**Decision**: Kubernetes is a dedicated learning project. Fargate lets this project stay focused on distributed systems patterns without node management distraction.

---

## Architecture

```text
Internet
    │
    ▼
Route 53 (CNAME → ALB)
    │
    ▼
Application Load Balancer  ← public subnets (2 AZs)
    │ HTTPS:443
    ▼
ECS Service: ingestor      ← private subnets (2 AZs)
    │                         Fargate Spot (dev) / Fargate (prod)
    ├── RDS PostgreSQL 17  ← private subnets, Multi-AZ in prod
    ├── ElastiCache Redis  ← private subnets
    └── MSK Serverless     ← private subnets (Kafka-compatible, IAM auth)
```

---

## Module Structure

```text
infra/terraform/
├── main.tf               # Provider + backend config (template only)
├── variables.tf          # Shared variable declarations
├── outputs.tf            # Root outputs
├── modules/
│   ├── network/          # VPC, subnets, IGW, NAT, security groups
│   ├── ecr/              # ECR repos for all 5 services (lifecycle policies)
│   ├── iam/              # GitHub Actions OIDC provider + role
│   ├── database/         # RDS PostgreSQL 17 (gp3, encrypted, Multi-AZ toggle)
│   ├── cache/            # ElastiCache Redis 7.1 (TLS, AUTH token)
│   ├── messaging/        # MSK Serverless (IAM auth, Kafka-compatible)
│   └── compute/          # ECS cluster, ALB, task definitions, services
└── environments/
    ├── dev/              # dev sizing: db.t3.micro, 1 NAT GW, Fargate Spot
    └── prod/             # prod sizing: db.t3.medium, Multi-AZ, 3 AZs
```

---

## First-Time Setup

### 1. AWS Profile Setup (local machine)

Create a **named profile** for this project. Never use the `default` profile for project work — it avoids cross-project credential confusion.

```bash
# Add to ~/.aws/config
[profile data-zoo-dev]
region = eu-central-1
output = json
# sso_start_url = https://your-org.awsapps.com/start  # If using SSO

[profile data-zoo-prod]
region = eu-central-1
output = json
```

```bash
# Add to ~/.aws/credentials (long-lived keys — prefer SSO or aws-vault instead)
[data-zoo-dev]
aws_access_key_id     = AKIA...
aws_secret_access_key = ...

[data-zoo-prod]
aws_access_key_id     = AKIA...
aws_secret_access_key = ...
```

> **Recommendation on your old profiles**: Run `aws configure list-profiles` and audit `~/.aws/credentials`. For any profile tied to a project you no longer actively use, rotate or delete the access keys in IAM. Stale keys are a security liability.

### 2. Better option: aws-vault

[aws-vault](https://github.com/99designs/aws-vault) stores credentials in your OS keychain (not plaintext in `~/.aws/credentials`) and injects temporary STS tokens per command:

```bash
brew install aws-vault                          # macOS
aws-vault add data-zoo-dev                      # prompts for key ID + secret
aws-vault exec data-zoo-dev -- terraform plan   # injects temp creds
```

Benefits:

- Keys never touch disk in plaintext
- Auto-refreshes STS tokens
- Per-profile MFA enforcement possible
- Audit trail (every assume-role logged in CloudTrail)

### 3. Create S3 Backend Bucket + DynamoDB Lock Table

Run once per AWS account. Use the `data-zoo-dev` profile:

```bash
aws s3api create-bucket \
  --bucket data-zoo-terraform-state-dev \
  --region eu-central-1 \
  --profile data-zoo-dev

aws s3api put-bucket-versioning \
  --bucket data-zoo-terraform-state-dev \
  --versioning-configuration Status=Enabled \
  --profile data-zoo-dev

aws s3api put-bucket-encryption \
  --bucket data-zoo-terraform-state-dev \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' \
  --profile data-zoo-dev

aws dynamodb create-table \
  --table-name data-zoo-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --profile data-zoo-dev
```

### 4. Configure GitHub Actions Variables and Secrets

Set these in GitHub → Settings → Secrets and variables → Actions.

Repository-level values:

| Type | Name | Example | Notes |
| ---- | ---- | ------- | ----- |
| Variable | `AWS_REGION` | `eu-central-1` | Shared region default for build, promote, and deploy workflows |
| Secret | `AWS_ACCOUNT_ID` | `123456789012` | Required for ECR registry resolution |

Environment-level values (`dev`, `prod`):

| Type | Name | Example | Notes |
| ---- | ---- | ------- | ----- |
| Variable | `AWS_ROLE_ARN` | `arn:aws:iam::123456789012:role/data-zoo-github-actions` | OIDC role assumed by GitHub Actions |
| Variable | `ECS_CLUSTER_NAME` | `data-zoo-dev` | Cluster target for deploy workflow |
| Variable | `ECS_SERVICE_NAME` | `ingestor` | Default ingestor ECS service |
| Variable | `ECS_TASK_DEFINITION_FAMILY` | `ingestor` | Default ingestor task definition family |
| Variable | `ECS_SERVICE_NAME_AI_GATEWAY` | `ai-gateway` | Per-service deploy target |
| Variable | `ECS_TASK_DEFINITION_FAMILY_AI_GATEWAY` | `ai-gateway` | Per-service task definition family |
| Variable | `ECS_SERVICE_NAME_QUERY_API` | `query-api` | Per-service deploy target |
| Variable | `ECS_TASK_DEFINITION_FAMILY_QUERY_API` | `query-api` | Per-service task definition family |
| Variable | `ECS_SERVICE_NAME_PROCESSOR` | `processor` | Per-service deploy target |
| Variable | `ECS_TASK_DEFINITION_FAMILY_PROCESSOR` | `processor` | Per-service task definition family |
| Variable | `ECS_SERVICE_NAME_DASHBOARD` | `dashboard` | Per-service deploy target |
| Variable | `ECS_TASK_DEFINITION_FAMILY_DASHBOARD` | `dashboard` | Per-service task definition family |
| Variable | `COSIGN_CERTIFICATE_IDENTITY` | workflow identity URL | Signature verification policy for deploy workflow |

**No `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in GitHub Secrets.** The OIDC role replaces long-lived keys entirely.

### 5. Apply Terraform (dev)

```bash
cd infra/terraform/environments/dev

# Init with backend config
terraform init \
  -backend-config="bucket=data-zoo-terraform-state-dev" \
  -backend-config="key=data-zoo/dev/terraform.tfstate" \
  -backend-config="region=eu-central-1" \
  -backend-config="dynamodb_table=data-zoo-terraform-locks"

# Copy example and fill in your values
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set acm_certificate_arn at minimum

# Supply sensitive vars via environment
export TF_VAR_redis_auth_token=$(openssl rand -hex 32)
# Store it: aws ssm put-parameter --name /data-zoo/dev/redis-auth-token \
#   --value "$TF_VAR_redis_auth_token" --type SecureString --profile data-zoo-dev

terraform plan
terraform apply
```

---

## Current Delivery Flow

The repository now uses four separate workflow stages instead of one workflow with commented deploy steps:

1. [CI workflow](../.github/workflows/ci.yml): queued quality, unit, migrations, integration, e2e, PR dependency audit, then build-only image validation on push
2. [Manual Docker Build](../.github/workflows/docker-build.yml): manual build or build+push for one service or all services
3. [Release Promote](../.github/workflows/release-promote.yml): manual promotion of one service or all services by digest/tag
4. [CD Deploy](../.github/workflows/cd-deploy.yml): manual per-service ECS deployment to `dev` or `prod`

Manual deploy example:

```bash
aws ecs update-service \
  --cluster data-zoo-dev \
  --service ingestor \
  --force-new-deployment \
  --region eu-central-1 \
  --profile data-zoo-dev

# Watch rollout
aws ecs wait services-stable \
  --cluster data-zoo-dev \
  --services ingestor \
  --region eu-central-1 \
  --profile data-zoo-dev
```

---

## Enabling CD from GitHub Actions

When you're ready to use the current GitHub Actions delivery path end-to-end:

1. Uncomment `aws_iam_role_policy.ecs_deploy` in `infra/terraform/modules/iam/main.tf`
2. Re-apply Terraform: `terraform apply`
3. Verify the role now has `ecs:UpdateService` permission:

   ```bash
   aws iam simulate-principal-policy \
     --policy-source-arn $(terraform output -raw github_actions_role_arn) \
     --action-names ecs:UpdateService \
      --resource-arns "arn:aws:ecs:eu-central-1:*:service/data-zoo-dev/ingestor"
   ```

4. Ensure GitHub Actions variables and secrets are populated for the target environment
5. Run `docker-build.yml` manually with `push_image=true`
6. Run `release-promote.yml` for the image you want to tag for `dev` or `prod`
7. Run `cd-deploy.yml` and choose the exact service and environment to deploy

---

## Secrets Management Strategy

All runtime secrets are stored in **AWS Secrets Manager** (not SSM Parameter Store, not environment variables in task definitions):

| Secret path                     | Contains                    | Injected via                     |
| ------------------------------- | --------------------------- | -------------------------------- |
| `data-zoo/dev/database-url`     | `postgresql+asyncpg://...`  | ECS `secrets` in task definition |
| `data-zoo/dev/redis-url`        | `rediss://:token@host:6379` | ECS `secrets` in task definition |
| `data-zoo/dev/redis-auth-token` | Redis AUTH token (hex)      | Read during Terraform apply      |

ECS injects these into containers as environment variables at start-time. The values are **never visible in the task definition JSON, CloudWatch logs, or Terraform state** (the task definition only stores the secret ARN).

### Why Secrets Manager over SSM Parameter Store?

- Automatic rotation support (RDS, ElastiCache, custom Lambda)
- Cross-account access via resource policies
- Native RDS managed password integration (`manage_master_user_password = true`)
- Slightly higher cost but justified for production

### Local development

Use `.env` (gitignored) for local dev secrets. Never copy production secrets to `.env`.

```bash
# .env (never committed)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline
REDIS_URL=redis://localhost:6379
```

---

## Cost Estimates (eu-central-1, ~2026 pricing)

### Dev environment (minimal)

| Service           | Config                     | Est. monthly   |
| ----------------- | -------------------------- | -------------- |
| ECS Fargate Spot  | 1 task, 0.25 vCPU, 512 MiB | ~$3            |
| RDS PostgreSQL    | db.t3.micro, 20 GB gp3     | ~$15           |
| ElastiCache Redis | cache.t3.micro, 1 node     | ~$12           |
| MSK Serverless    | ~1 GB/month                | ~$1            |
| NAT Gateway       | 1 AZ, ~10 GB               | ~$35           |
| ALB               | ~1 LCU                     | ~$18           |
| **Total dev**     |                            | **~$84/month** |

> The NAT Gateway dominates dev costs. Consider VPC endpoints for ECR/S3 to reduce data transfer charges once running.

### Prod environment (HA)

| Service           | Config                        | Est. monthly    |
| ----------------- | ----------------------------- | --------------- |
| ECS Fargate       | 2 tasks, 0.5 vCPU, 1 GiB      | ~$25            |
| RDS PostgreSQL    | db.t3.medium, Multi-AZ, 20 GB | ~$75            |
| ElastiCache Redis | cache.t3.small, 2 nodes       | ~$40            |
| MSK Serverless    | ~10 GB/month                  | ~$10            |
| NAT Gateway       | 3 AZs                         | ~$100           |
| ALB               | ~5 LCUs                       | ~$25            |
| **Total prod**    |                               | **~$275/month** |

---

## Teardown

```bash
cd infra/terraform/environments/dev
terraform destroy

# Empty the S3 state bucket before destroying it (versioned buckets can't be deleted with objects)
aws s3 rm s3://data-zoo-terraform-state-dev --recursive --profile data-zoo-dev
```
