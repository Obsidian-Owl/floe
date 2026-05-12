# AWS Provider Test Account Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable, low-cost AWS provider testing setup for Floe using OpenTofu, a minimal human handoff guide, and a reusable Codex skill.

**Architecture:** Keep the human-facing guide small and make automation the source of truth. OpenTofu owns AWS setup, shell helpers own readiness/cleanup checks, and the Codex skill owns the repeatable agent workflow. The default path provisions no always-on compute and does not replace the existing Hetzner DevPod control lane.

**Tech Stack:** OpenTofu, AWS provider, AWS CLI, Bash, Markdown docs, Codex skill format, existing Floe docs validators and pre-commit hooks.

---

## Scope And File Map

Create:

- `infra/aws-provider-tests/versions.tf` - OpenTofu and AWS provider requirements.
- `infra/aws-provider-tests/variables.tf` - configurable inputs with safe defaults and validation.
- `infra/aws-provider-tests/locals.tf` - normalized names and common tags.
- `infra/aws-provider-tests/main.tf` - S3 bucket, encryption, public access block, lifecycle, and budget resources.
- `infra/aws-provider-tests/iam.tf` - scoped IAM policy/role and optional disabled-by-default access-key user.
- `infra/aws-provider-tests/outputs.tf` - environment hints for agents and contributors.
- `infra/aws-provider-tests/terraform.tfvars.example` - copyable non-secret example values.
- `infra/aws-provider-tests/README.md` - short IaC owner notes for agents.
- `scripts/aws-provider-test-readiness.sh` - AWS account, S3, Glue, Budget, and IAM readiness checks.
- `scripts/aws-provider-test-cleanup.sh` - current-run S3/Glue cleanup plus post-cleanup inventory.
- `docs/contributing/aws-provider-testing.md` - human-only prerequisite and handoff guide.
- `.codex/skills/floe-aws-provider-testing/SKILL.md` - reusable agent workflow skill.

Modify:

- `.gitignore` - allow committing `infra/aws-provider-tests/.terraform.lock.hcl` while keeping state and local tfvars ignored.
- `docs/contributing/index.md` - link the AWS provider testing guide.

Do not create:

- EKS resources.
- NAT Gateways.
- Glue jobs or crawlers.
- Lake Formation or S3 Tables resources.
- Long-running EC2 resources.
- Real AWS credentials, tfstate, or local-only tfvars in git.

## Task 1: Add OpenTofu Scaffold

**Files:**

- Create: `infra/aws-provider-tests/versions.tf`
- Create: `infra/aws-provider-tests/variables.tf`
- Create: `infra/aws-provider-tests/locals.tf`
- Create: `infra/aws-provider-tests/main.tf`
- Create: `infra/aws-provider-tests/iam.tf`
- Create: `infra/aws-provider-tests/outputs.tf`
- Create: `infra/aws-provider-tests/terraform.tfvars.example`
- Create: `infra/aws-provider-tests/README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Create the OpenTofu directory**

Run:

```bash
mkdir -p infra/aws-provider-tests
```

Expected: directory exists and contains no files yet.

- [ ] **Step 2: Add provider requirements**

Create `infra/aws-provider-tests/versions.tf`:

```hcl
terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 7.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}
```

- [ ] **Step 3: Add variables with validation**

Create `infra/aws-provider-tests/variables.tf`:

```hcl
variable "aws_region" {
  description = "AWS region used for Floe provider compatibility testing."
  type        = string
  default     = "ap-southeast-2"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be an AWS region identifier such as ap-southeast-2."
  }
}

variable "name_prefix" {
  description = "Prefix for AWS resources created by this scaffold."
  type        = string
  default     = "floe-provider-tests"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,40}$", var.name_prefix))
    error_message = "name_prefix must be lowercase, start with a letter, and contain only letters, numbers, and hyphens."
  }
}

variable "owner" {
  description = "Human owner for cost and cleanup accountability."
  type        = string
}

variable "budget_email" {
  description = "Email address that receives AWS Budget alerts."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.budget_email))
    error_message = "budget_email must be an email address."
  }
}

variable "monthly_budget_limit_usd" {
  description = "Monthly AWS Budget threshold in USD."
  type        = number
  default     = 25

  validation {
    condition     = var.monthly_budget_limit_usd > 0 && var.monthly_budget_limit_usd <= 100
    error_message = "monthly_budget_limit_usd must be greater than 0 and no more than 100 for this test scaffold."
  }
}

variable "s3_bucket_name" {
  description = "Optional explicit S3 bucket name. Leave null to derive one from account, region, and prefix."
  type        = string
  default     = null
}

variable "s3_run_prefix" {
  description = "S3 prefix under which per-run test artifacts are written."
  type        = string
  default     = "runs/"

  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9/_-]*/$", var.s3_run_prefix))
    error_message = "s3_run_prefix must be a relative S3 prefix ending with /."
  }
}

variable "run_data_retention_days" {
  description = "Number of days before S3 run data expires."
  type        = number
  default     = 3

  validation {
    condition     = var.run_data_retention_days >= 1 && var.run_data_retention_days <= 30
    error_message = "run_data_retention_days must be between 1 and 30."
  }
}

variable "glue_database_prefix" {
  description = "Prefix allowed for Glue databases created by provider tests."
  type        = string
  default     = "floe_provider_"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{2,40}_$", var.glue_database_prefix))
    error_message = "glue_database_prefix must be lowercase snake_case and end with an underscore."
  }
}

variable "enable_access_key_user" {
  description = "Create a disabled-by-default IAM user/access key path for environments that cannot assume roles."
  type        = bool
  default     = false
}

variable "enable_aws_devpod_permissions" {
  description = "Include EC2 permissions needed by a future AWS DevPod target."
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Additional tags applied to supported AWS resources."
  type        = map(string)
  default     = {}
}
```

- [ ] **Step 4: Add locals**

Create `infra/aws-provider-tests/locals.tf`:

```hcl
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  derived_bucket_name = lower("${var.name_prefix}-${local.account_id}-${var.aws_region}")
  bucket_name         = coalesce(var.s3_bucket_name, local.derived_bucket_name)

  common_tags = merge(
    {
      Project   = "floe"
      Purpose   = "provider-compatibility"
      ManagedBy = "opentofu"
      Owner     = var.owner
    },
    var.common_tags,
  )
}
```

- [ ] **Step 5: Add S3 and Budget resources**

Create `infra/aws-provider-tests/main.tf`:

```hcl
resource "aws_s3_bucket" "provider_tests" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_public_access_block" "provider_tests" {
  bucket = aws_s3_bucket.provider_tests.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "provider_tests" {
  bucket = aws_s3_bucket.provider_tests.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "provider_tests" {
  bucket = aws_s3_bucket.provider_tests.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "provider_tests" {
  bucket = aws_s3_bucket.provider_tests.id

  rule {
    id     = "expire-provider-test-runs"
    status = "Enabled"

    filter {
      prefix = var.s3_run_prefix
    }

    expiration {
      days = var.run_data_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_budgets_budget" "provider_tests" {
  name         = "${var.name_prefix}-monthly-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}
```

- [ ] **Step 6: Add scoped IAM resources**

Create `infra/aws-provider-tests/iam.tf`:

```hcl
data "aws_iam_policy_document" "provider_test_permissions" {
  statement {
    sid = "ReadCallerIdentity"

    actions = [
      "sts:GetCallerIdentity",
    ]

    resources = ["*"]
  }

  statement {
    sid = "ListProviderTestBucket"

    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.provider_tests.arn,
    ]
  }

  statement {
    sid = "ManageProviderTestObjects"

    actions = [
      "s3:AbortMultipartUpload",
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:ListMultipartUploadParts",
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.provider_tests.arn}/${var.s3_run_prefix}*",
    ]
  }

  statement {
    sid = "ManageFloeGlueDatabases"

    actions = [
      "glue:CreateDatabase",
      "glue:DeleteDatabase",
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:UpdateDatabase",
    ]

    resources = [
      "arn:aws:glue:${var.aws_region}:${local.account_id}:catalog",
      "arn:aws:glue:${var.aws_region}:${local.account_id}:database/${var.glue_database_prefix}*",
    ]
  }

  statement {
    sid = "ManageFloeGlueTables"

    actions = [
      "glue:BatchDeleteTable",
      "glue:CreateTable",
      "glue:DeleteTable",
      "glue:GetTable",
      "glue:GetTables",
      "glue:UpdateTable",
    ]

    resources = [
      "arn:aws:glue:${var.aws_region}:${local.account_id}:catalog",
      "arn:aws:glue:${var.aws_region}:${local.account_id}:database/${var.glue_database_prefix}*",
      "arn:aws:glue:${var.aws_region}:${local.account_id}:table/${var.glue_database_prefix}*/*",
    ]
  }

  dynamic "statement" {
    for_each = var.enable_aws_devpod_permissions ? [1] : []

    content {
      sid = "OptionalAwsDevPodEc2Inventory"

      actions = [
        "ec2:DescribeInstances",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeVolumes",
        "ec2:DescribeVpcs",
      ]

      resources = ["*"]
    }
  }
}

resource "aws_iam_policy" "provider_test_permissions" {
  name        = "${var.name_prefix}-permissions"
  description = "Scoped permissions for Floe AWS provider compatibility tests."
  policy      = data.aws_iam_policy_document.provider_test_permissions.json
}

resource "aws_iam_user" "provider_test" {
  count = var.enable_access_key_user ? 1 : 0
  name  = "${var.name_prefix}-user"
}

resource "aws_iam_user_policy_attachment" "provider_test" {
  count      = var.enable_access_key_user ? 1 : 0
  user       = aws_iam_user.provider_test[0].name
  policy_arn = aws_iam_policy.provider_test_permissions.arn
}
```

Do not create an access key resource in the first implementation. If a user path needs access keys later, add it behind a separate approval because Terraform state would contain the secret access key.

- [ ] **Step 7: Add outputs**

Create `infra/aws-provider-tests/outputs.tf`:

```hcl
output "aws_account_id" {
  description = "AWS account ID where provider-test resources were created."
  value       = local.account_id
}

output "aws_region" {
  description = "AWS region for provider-test resources."
  value       = var.aws_region
}

output "s3_bucket_name" {
  description = "Reusable S3 bucket for Floe provider compatibility tests."
  value       = aws_s3_bucket.provider_tests.bucket
}

output "s3_run_prefix" {
  description = "Prefix for per-run S3 data."
  value       = var.s3_run_prefix
}

output "glue_database_prefix" {
  description = "Allowed Glue database prefix for provider tests."
  value       = var.glue_database_prefix
}

output "provider_test_policy_arn" {
  description = "IAM policy ARN for Floe AWS provider tests."
  value       = aws_iam_policy.provider_test_permissions.arn
}

output "recommended_environment" {
  description = "Non-secret environment exports for Floe AWS provider validation."
  value = {
    FLOE_AWS_REGION               = var.aws_region
    FLOE_AWS_TEST_BUCKET          = aws_s3_bucket.provider_tests.bucket
    FLOE_AWS_TEST_PREFIX          = var.s3_run_prefix
    FLOE_AWS_GLUE_DATABASE_PREFIX = var.glue_database_prefix
  }
}
```

- [ ] **Step 8: Add example tfvars**

Create `infra/aws-provider-tests/terraform.tfvars.example`:

```hcl
aws_region               = "ap-southeast-2"
name_prefix              = "floe-provider-tests"
owner                    = "your-name"
budget_email             = "you@example.com"
monthly_budget_limit_usd = 25
run_data_retention_days  = 3
glue_database_prefix     = "floe_provider_"

common_tags = {
  Environment = "test"
  CostCenter  = "floe-provider-tests"
}
```

- [ ] **Step 9: Add IaC README**

Create `infra/aws-provider-tests/README.md`:

~~~markdown
# Floe AWS Provider Test Account

This OpenTofu scaffold prepares low-cost AWS resources for Floe provider
compatibility validation.

It creates S3, IAM, and Budget resources only. It does not create EKS, EC2,
NAT Gateways, Glue jobs, Glue crawlers, Lake Formation resources, or S3 Tables.

## Human prerequisites

Read `docs/contributing/aws-provider-testing.md` before applying this scaffold.

## Agent workflow

```bash
cd infra/aws-provider-tests
cp terraform.tfvars.example terraform.tfvars
tofu init
tofu fmt -check
tofu validate
tofu plan -out tfplan
tofu apply tfplan
```

Do not commit `terraform.tfvars`, `tfplan`, `.terraform/`, or state files.
~~~

- [ ] **Step 10: Allow committing the OpenTofu lock file for this scaffold**

Modify the Terraform section in `.gitignore`:

```gitignore
# Terraform / OpenTofu
.terraform/
*.tfstate
*.tfstate.*
.terraform.lock.hcl
!infra/aws-provider-tests/.terraform.lock.hcl
*.tfvars
!*.tfvars.example
tfplan
*.tfplan
```

- [ ] **Step 11: Format and validate OpenTofu files**

Run:

```bash
tofu fmt -check infra/aws-provider-tests
tofu init -backend=false -chdir=infra/aws-provider-tests
tofu validate -chdir=infra/aws-provider-tests
```

Expected:

- `tofu fmt -check` exits `0`.
- `tofu init -backend=false` installs provider metadata locally.
- `tofu validate` reports success.

If `tofu` is not installed, record `SKIP: tofu CLI unavailable` in the task notes and continue to docs/secret validation. Do not replace OpenTofu with Terraform.

- [ ] **Step 12: Commit OpenTofu scaffold**

Run:

```bash
git add .gitignore infra/aws-provider-tests
git commit -m "infra: add AWS provider test scaffold"
```

## Task 2: Add AWS Readiness And Cleanup Helpers

**Files:**

- Create: `scripts/aws-provider-test-readiness.sh`
- Create: `scripts/aws-provider-test-cleanup.sh`

- [ ] **Step 1: Add readiness helper**

Create `scripts/aws-provider-test-readiness.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

log() {
    echo "[aws-provider-readiness] $*" >&2
}

require_env() {
    local name="$1"
    if [[ -z "${!name:-}" ]]; then
        echo "[aws-provider-readiness] ERROR: ${name} is required" >&2
        exit 1
    fi
}

require_env FLOE_AWS_REGION
require_env FLOE_AWS_TEST_BUCKET
require_env FLOE_AWS_GLUE_DATABASE_PREFIX

aws_args=(--region "${FLOE_AWS_REGION}")

log "Checking AWS caller identity"
aws sts get-caller-identity "${aws_args[@]}"

log "Checking S3 bucket access: ${FLOE_AWS_TEST_BUCKET}"
aws s3api get-bucket-location \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    "${aws_args[@]}"

log "Checking S3 list access"
aws s3api list-objects-v2 \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    --prefix "${FLOE_AWS_TEST_PREFIX:-runs/}" \
    --max-items 1 \
    "${aws_args[@]}" >/dev/null

probe_db="${FLOE_AWS_GLUE_DATABASE_PREFIX}readiness_$(date -u +%Y%m%d%H%M%S)"

cleanup_probe() {
    aws glue delete-database \
        --database-name "${probe_db}" \
        "${aws_args[@]}" >/dev/null 2>&1 || true
}
trap cleanup_probe EXIT

log "Checking Glue create/get/delete access with ${probe_db}"
aws glue create-database \
    --database-input "{\"Name\":\"${probe_db}\"}" \
    "${aws_args[@]}" >/dev/null
aws glue get-database \
    --name "${probe_db}" \
    "${aws_args[@]}" >/dev/null
aws glue delete-database \
    --database-name "${probe_db}" \
    "${aws_args[@]}" >/dev/null

log "Readiness checks passed"
```

- [ ] **Step 2: Add cleanup helper**

Create `scripts/aws-provider-test-cleanup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

log() {
    echo "[aws-provider-cleanup] $*" >&2
}

require_env() {
    local name="$1"
    if [[ -z "${!name:-}" ]]; then
        echo "[aws-provider-cleanup] ERROR: ${name} is required" >&2
        exit 1
    fi
}

require_env FLOE_AWS_REGION
require_env FLOE_AWS_TEST_BUCKET
require_env FLOE_AWS_GLUE_DATABASE_PREFIX
require_env FLOE_PROVIDER_SPIKE_RUN

aws_args=(--region "${FLOE_AWS_REGION}")
run_prefix="${FLOE_AWS_TEST_PREFIX:-runs/}${FLOE_PROVIDER_SPIKE_RUN}/"
run_database="${FLOE_AWS_GLUE_DATABASE_PREFIX}${FLOE_PROVIDER_SPIKE_RUN//-/_}"

log "Cleaning S3 run prefix s3://${FLOE_AWS_TEST_BUCKET}/${run_prefix}"
aws s3 rm "s3://${FLOE_AWS_TEST_BUCKET}/${run_prefix}" --recursive "${aws_args[@]}" || true

log "Deleting Glue tables in ${run_database} if the database exists"
if aws glue get-database --name "${run_database}" "${aws_args[@]}" >/dev/null 2>&1; then
    table_names="$(
        aws glue get-tables \
            --database-name "${run_database}" \
            --query 'TableList[].Name' \
            --output text \
            "${aws_args[@]}"
    )"
    for table_name in ${table_names}; do
        aws glue delete-table \
            --database-name "${run_database}" \
            --name "${table_name}" \
            "${aws_args[@]}" >/dev/null || true
    done
    aws glue delete-database \
        --database-name "${run_database}" \
        "${aws_args[@]}" >/dev/null || true
fi

log "Post-cleanup S3 inventory"
aws s3api list-objects-v2 \
    --bucket "${FLOE_AWS_TEST_BUCKET}" \
    --prefix "${run_prefix}" \
    --max-items 10 \
    "${aws_args[@]}"

log "Post-cleanup Glue inventory"
aws glue get-database \
    --name "${run_database}" \
    "${aws_args[@]}" >/dev/null 2>&1 && {
        echo "[aws-provider-cleanup] ERROR: Glue database still exists: ${run_database}" >&2
        exit 1
    }

log "Cleanup checks passed"
```

- [ ] **Step 3: Make helpers executable and lint shell syntax**

Run:

```bash
chmod +x scripts/aws-provider-test-readiness.sh scripts/aws-provider-test-cleanup.sh
bash -n scripts/aws-provider-test-readiness.sh
bash -n scripts/aws-provider-test-cleanup.sh
```

Expected: both `bash -n` commands exit `0`.

- [ ] **Step 4: Commit helpers**

Run:

```bash
git add scripts/aws-provider-test-readiness.sh scripts/aws-provider-test-cleanup.sh
git commit -m "tools: add AWS provider test helpers"
```

## Task 3: Add Minimal Human Guide

**Files:**

- Create: `docs/contributing/aws-provider-testing.md`
- Modify: `docs/contributing/index.md`

- [ ] **Step 1: Add contributor guide**

Create `docs/contributing/aws-provider-testing.md`:

```markdown
# AWS Provider Testing

Use this guide when you want an AI agent to set up the AWS side of Floe
provider compatibility testing.

This is not a product deployment guide. The default setup creates no EKS
cluster, no NAT Gateway, no Glue jobs, no Glue crawlers, and no always-on EC2.

## What A Human Must Provide

Before asking an agent to set up AWS provider tests, have these ready:

| Requirement | Why it matters |
| --- | --- |
| AWS sandbox account | Tests create and delete S3 and Glue resources. Do not use production. |
| Approved AWS region | Keeps bucket, Glue, and cost evidence consistent. |
| AWS CLI profile or SSO session | Lets the agent run OpenTofu and AWS CLI checks. |
| Permission to manage IAM, S3, Glue, and Budgets | The scaffold creates the scoped test resources and cost alarm. |
| Budget alert email | OpenTofu creates a low monthly AWS Budget. |
| Owner name/tag | Every created resource is tagged for accountability. |

Do not provide raw access keys in chat. Use a local AWS profile or SSO session
that the agent can use from the repository workspace.

## What The Agent Will Create

The agent applies `infra/aws-provider-tests/` with OpenTofu. The scaffold
creates:

- one reusable S3 bucket for provider-test data;
- S3 public access block, encryption, and lifecycle expiry for `runs/`;
- scoped IAM policy resources for S3 and Glue provider tests;
- a low monthly AWS Budget;
- non-secret outputs used by Floe provider validation.

## What The Agent Must Not Create By Default

- EKS clusters
- NAT Gateways
- always-on EC2 instances
- Glue jobs or crawlers
- Lake Formation resources
- S3 Tables resources
- AWS access keys stored in OpenTofu state

## Handoff Prompt

Use this prompt when asking an agent to set up the environment:

```text
Set up the Floe AWS provider testing environment from /Users/dmccarthy/Projects/floe.
Use AWS profile <profile-name>, region <region>, owner <owner>, and budget email <email>.
Use OpenTofu under infra/aws-provider-tests.
Do not create EKS, NAT Gateway, Glue jobs, Glue crawlers, Lake Formation, S3 Tables, or always-on EC2.
Run readiness checks and report the AWS account ID, region, bucket, Glue database prefix, and cleanup status.
```

## Clean Account Check

After a run, ask the agent to verify:

```bash
aws sts get-caller-identity
scripts/aws-provider-test-cleanup.sh
```

The final report must say whether current-run S3 prefixes and Glue databases
were removed.
```

- [ ] **Step 2: Link the guide from contributor index**

Modify the Contributor Workflows list in `docs/contributing/index.md` to include:

```markdown
- [AWS provider testing](aws-provider-testing.md) for the human prerequisites needed before an agent provisions the AWS test environment.
```

- [ ] **Step 3: Run docs validators**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
```

Expected: both commands pass.

- [ ] **Step 4: Commit guide**

Run:

```bash
git add docs/contributing/aws-provider-testing.md docs/contributing/index.md
git commit -m "docs: add AWS provider testing handoff guide"
```

## Task 4: Add Reusable Codex Skill

**Files:**

- Create: `.codex/skills/floe-aws-provider-testing/SKILL.md`

- [ ] **Step 1: Create skill directory**

Run:

```bash
mkdir -p .codex/skills/floe-aws-provider-testing
```

- [ ] **Step 2: Add skill instructions**

Create `.codex/skills/floe-aws-provider-testing/SKILL.md`:

```markdown
---
name: floe-aws-provider-testing
description: Use when setting up, validating, running, or cleaning up Floe AWS provider testing through infra/aws-provider-tests. Applies to AWS S3 plus AWS Glue provider compatibility work, OpenTofu scaffold operations, AWS readiness checks, and cleanup evidence.
---

# Floe AWS Provider Testing

Use this skill for Floe AWS provider test-account setup and cleanup.

## Preconditions

- Work from `/Users/dmccarthy/Projects/floe` unless the user gives another Floe checkout.
- Read `docs/contributing/aws-provider-testing.md`.
- Use `infra/aws-provider-tests` for OpenTofu.
- Confirm the AWS account is a sandbox or approved test account.
- Confirm region, owner, budget email, and AWS profile.
- Do not use production data.
- Do not create EKS, NAT Gateway, Glue jobs, Glue crawlers, Lake Formation, S3 Tables, or always-on EC2 unless the user explicitly approves a separate design.

## Setup Workflow

1. Run `aws sts get-caller-identity --profile <profile>` and confirm the account with the user-provided target.
2. Copy `infra/aws-provider-tests/terraform.tfvars.example` to `infra/aws-provider-tests/terraform.tfvars` if no local tfvars exists.
3. Fill only non-secret values: region, owner, budget email, and tags.
4. Run:

```bash
cd infra/aws-provider-tests
AWS_PROFILE=<profile> tofu init
AWS_PROFILE=<profile> tofu fmt -check
AWS_PROFILE=<profile> tofu validate
AWS_PROFILE=<profile> tofu plan -out tfplan
```

5. Review the plan for allowed resource classes only: S3, IAM policy/user attachment if enabled, Budget.
6. Run `AWS_PROFILE=<profile> tofu apply tfplan` only after the plan is acceptable.
7. Export the non-secret outputs needed by validation:

```bash
export FLOE_AWS_REGION=<region>
export FLOE_AWS_TEST_BUCKET=<bucket>
export FLOE_AWS_TEST_PREFIX=runs/
export FLOE_AWS_GLUE_DATABASE_PREFIX=floe_provider_
```

8. Run `scripts/aws-provider-test-readiness.sh`.

## Cleanup Workflow

For a live provider run, set the current run ID:

```bash
export FLOE_PROVIDER_SPIKE_RUN=floe-provider-YYYYMMDDTHHMMSSZ
```

Then run:

```bash
scripts/aws-provider-test-cleanup.sh
```

If the whole scaffold is no longer needed:

```bash
cd infra/aws-provider-tests
AWS_PROFILE=<profile> tofu destroy
```

After cleanup, report S3, Glue, and any optional DevPod/EC2 inventory separately.

## Failure Classification

- Product failure: Floe resolver, binding, runtime translator, renderer, or plugin behavior is wrong.
- Provider failure: AWS auth, S3, Glue, IAM, region, endpoint, or API behavior rejects the test.
- Infrastructure failure: OpenTofu, DevPod, Kind, network, or CLI setup fails before product validation.
- Cleanup failure: current-run AWS resources remain after cleanup.
```

- [ ] **Step 3: Run skill hygiene checks**

Run:

```bash
test -f .codex/skills/floe-aws-provider-testing/SKILL.md
rg -n "AKIA|ASIA|aws_secret_access_key|AWS_SECRET_ACCESS_KEY|secret_access_key|BEGIN [A-Z ]*PRIVATE KEY" .codex/skills/floe-aws-provider-testing/SKILL.md
```

Expected:

- `test -f` exits `0`.
- `rg` exits `1` with no matches.

- [ ] **Step 4: Commit skill**

Run:

```bash
git add .codex/skills/floe-aws-provider-testing/SKILL.md
git commit -m "docs: add Floe AWS provider testing skill"
```

## Task 5: Final Validation And Evidence

**Files:**

- Validate all files changed by Tasks 1-4.
- Optionally create validation note only if a live AWS or OpenTofu command is skipped or fails for environmental reasons.

- [ ] **Step 1: Run static validation**

Run:

```bash
git status --short --branch
git diff --check HEAD
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
bash -n scripts/aws-provider-test-readiness.sh
bash -n scripts/aws-provider-test-cleanup.sh
```

Expected:

- Worktree shows only intended changes if any remain uncommitted.
- `git diff --check HEAD` reports no whitespace errors.
- Docs validators pass.
- Bash syntax checks pass.

- [ ] **Step 2: Run OpenTofu validation when the CLI is available**

Run:

```bash
tofu fmt -check infra/aws-provider-tests
tofu init -backend=false -chdir=infra/aws-provider-tests
tofu validate -chdir=infra/aws-provider-tests
```

Expected: all commands pass.

If `tofu` is unavailable, do not install tooling silently. Report:

```text
SKIP: OpenTofu validation not run because tofu CLI is unavailable.
```

- [ ] **Step 3: Run focused secret scan**

Run:

```bash
rg -n "AKIA|ASIA|aws_secret_access_key|AWS_SECRET_ACCESS_KEY|secret_access_key|BEGIN [A-Z ]*PRIVATE KEY|password\\s*=|token\\s*=|client_secret" \
  infra/aws-provider-tests \
  scripts/aws-provider-test-readiness.sh \
  scripts/aws-provider-test-cleanup.sh \
  docs/contributing/aws-provider-testing.md \
  .codex/skills/floe-aws-provider-testing/SKILL.md
```

Expected: no matches except non-secret explanatory text if explicitly reviewed. Prefer zero matches.

- [ ] **Step 4: Verify commit history and branch state**

Run:

```bash
git log --oneline -5
git status --short --branch
```

Expected:

- Recent commits include the OpenTofu scaffold, helper scripts, guide, and skill.
- Worktree is clean unless validation artifacts were intentionally left untracked.

## Plan Self-Review

Spec coverage:

- OpenTofu scaffold: Task 1.
- Minimal human guide: Task 3.
- Reusable Codex skill: Task 4.
- AWS readiness and cleanup evidence: Task 2 and Task 5.
- Cost controls and explicit exclusions: Task 1, Task 3, Task 4.
- No product provider implementation: out of scope in file map and tasks.

Placeholder scan:

- No placeholder-scan violations remain.
- Human-provided values appear only in guide/skill prompt examples as `<profile-name>`, `<region>`, `<owner>`, and `<email>`.

Execution note:

- The implementation should not run `tofu apply`, `tofu destroy`, or live AWS cleanup unless the user explicitly provides AWS account/profile details and authorizes live AWS mutation.
