# ADR 006: Terraform Remote S3 Backend with DynamoDB Locking vs Local State

**Date**: April 22, 2026
**Status**: Accepted
**Context**: Phase 7 requires team-safe infrastructure management. Terraform state must be safe from concurrent edits, versioned, and accessible across team members and CI/CD pipelines.

---

## Problem

Where should Terraform state be stored?

- **Local (default)**: `terraform.tfstate` in project directory
- **Remote S3 + DynamoDB**: State in S3 bucket, locks in DynamoDB table (team-safe)

---

## Decision

**Use remote S3 backend with DynamoDB state locking.**

### Rationale

| Factor | Local State | S3 + DynamoDB | Winner |
|--------|------------|---------------|--------|
| **Concurrent Edits** | Dangerous (merge conflicts) | Safe (DynamoDB mutex) | S3 + DDB |
| **Accidental Overwrite** | Easy (git merge, manual edit) | Prevented (lock prevents apply) | S3 + DDB |
| **Version History** | Manual (commit to git) | Automatic (S3 versioning) | S3 + DDB |
| **Team Collaboration** | Hard (one laptop owns state) | Easy (everyone reads from S3) | S3 + DDB |
| **CI/CD Integration** | Requires passing state file | State lives in AWS (CI/CD reads) | S3 + DDB |
| **Security** | Plaintext in git (secrets exposed) | Encrypted at rest, access controlled | S3 + DDB |
| **Setup Time** | 0 min (instant) | 15 min (create S3 bucket + DDB table) | Local |
| **Cost** | Free | ~$0.50/month (S3 storage + DDB) | Local |

### Why Remote S3 Backend?

1. **Prevents Concurrent Edits**
   - Two engineers can't apply Terraform simultaneously
   - DynamoDB `LockID` acts as mutex
   - One engineer acquires lock → applies → releases lock

2. **Team Scalability**
   - Any team member can deploy without needing state file
   - CI/CD pipeline automatically reads latest state
   - No "state file lives on Sarah's laptop" problem

3. **Disaster Recovery**
   - State versioned in S3 (unlimited snapshots)
   - Can revert to previous state if something broke
   - Audit trail of who deployed what when

4. **Security**
   - State file often contains secrets (database passwords, API keys)
   - S3 backend encrypts at rest (default AES-256)
   - Access controlled via IAM (not plaintext in git)

5. **CI/CD Integration**
   - GitHub Actions needs to read latest state
   - S3 backend seamlessly integrates via AWS credentials
   - No state file copying or checkout needed

---

## Implementation

### AWS Setup (one-time per account)

```bash
# Create S3 bucket for state
aws s3api create-bucket \
  --bucket data-zoo-terraform-state-dev \
  --region us-east-1

# Enable versioning (can revert to previous state)
aws s3api put-bucket-versioning \
  --bucket data-zoo-terraform-state-dev \
  --versioning-configuration Status=Enabled

# Enable encryption at rest
aws s3api put-bucket-encryption \
  --bucket data-zoo-terraform-state-dev \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name data-zoo-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### Terraform Configuration

```hcl
# infra/terraform/main.tf

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # These values passed via init flags (not hardcoded)
    # bucket         = "data-zoo-terraform-state-dev"
    # key            = "data-zoo/dev/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "data-zoo-terraform-locks"
    # encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

# Rest of Terraform code...
```

### First-Time Initialization

```bash
cd infra/terraform/environments/dev

terraform init \
  -backend-config="bucket=data-zoo-terraform-state-dev" \
  -backend-config="key=data-zoo/dev/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=data-zoo-terraform-locks" \
  -backend-config="encrypt=true"

# Subsequent runs don't need flags; Terraform reads state from S3
```

### .gitignore

```bash
# Never commit local state file
terraform.tfstate
terraform.tfstate.*
.terraform/
.terraform.lock.hcl

# OK to commit (for team visibility)
terraform.tfvars.example
```

---

## Consequences

### Positive

- ✅ **Prevents merge conflicts**: DynamoDB lock prevents concurrent applies
- ✅ **Team-safe**: Multiple engineers can deploy without state file conflicts
- ✅ **Audit trail**: S3 versioning + CloudTrail logs all changes
- ✅ **CI/CD friendly**: Pipeline doesn't need state file checked out
- ✅ **Secrets safe**: State encrypted in S3, never in git
- ✅ **Disaster recovery**: Can revert to any previous state snapshot

### Negative

- ❌ **Network dependency**: Terraform needs AWS credentials to read/write state
- ❌ **Setup overhead**: S3 bucket + DynamoDB table (15 min one-time)
- ❌ **Cost**: ~$0.50/month (negligible but non-zero)
- ❌ **Harder local debugging**: Can't inspect `.tfstate` file directly (it's in S3)
- ❌ **Destroy risks**: If S3 bucket deleted, state is lost (but S3 versioning helps)

---

## State File Security Warning

**Never commit `terraform.tfstate` to git!** It contains:

- ❌ Database passwords
- ❌ API keys
- ❌ Private key material
- ❌ OAuth tokens

If accidentally committed:

```bash
# Remove from git history (dangerous, requires force-push)
git filter-branch --tree-filter 'rm -f terraform.tfstate' HEAD
git push origin --force-all

# Rotate all secrets immediately
# (assume someone has seen the credentials)
```

---

## When Local State Is OK

1. **Throwaway environments** (local dev, testing)
2. **Solo developer** (no team collaboration)
3. **No secrets in state** (hard-coded values only)
4. **No CI/CD** (never deployed automatically)

**For any production or team project: use remote state.**

---

## Migration Path (if switching from local)

1. **Create S3 bucket + DDB table** (use script above)
2. **Initialize with remote backend** (Terraform automatically migrates)
3. **Verify state in S3** (`aws s3 ls` + `aws dynamodb get-item`)
4. **Delete local state file** (after confirming S3 copy exists)
5. **Commit `.gitignore` changes** (prevent accidental commits)
6. **Team members** do `terraform init` to sync

---

## Alternatives Considered

### 1. Local State File (Committed to Git)
- ✅ Zero setup
- ❌ Secrets exposed in git
- ❌ Merge conflicts if two people deploy simultaneously
- ❌ No versioning
- ❌ CI/CD can't read latest state

### 2. Terraform Cloud / Enterprise
- ✅ Fully managed (no bucket setup)
- ✅ Great UI + state history
- ❌ Requires subscription ($20+/month)
- ❌ Vendor lock-in (state lives on Terraform Cloud)

### 3. Other Backends (Azure Blob Storage, GCS, etc.)
- ✅ Works if already using Azure/GCP
- ❌ Overkill if only using AWS
- ❌ Requires learning another cloud

---

## Related Decisions

- [ADR 004: ECS Fargate vs EKS](004-ecs-fargate-vs-eks.md) (what we're managing with Terraform)
- [ADR 005: GitHub OIDC vs Long-Lived Keys](005-github-oidc-vs-long-lived-keys.md) (how CI/CD accesses state)
- [Phase 7: Cloud Deployment](../../cloud-deployment.md) (complete S3 backend setup guide)

---

## References

- [Terraform S3 Backend Documentation](https://www.terraform.io/language/settings/backends/s3)
- [Terraform State Locking](https://www.terraform.io/language/state/locking)
- [AWS S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [Terraform State Best Practices](https://www.terraform.io/language/state)
- [DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)
