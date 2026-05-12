# AWS Provider Test Account Design

## Goal

Create a repeatable, low-cost AWS test-account setup for Floe provider
compatibility validation. The setup must let an AI agent provision and validate
the AWS testing environment with minimal human setup, while keeping the human
guide focused on the AWS account prerequisites that cannot safely be automated
from inside the repository.

This design supports the deferred AWS S3 plus AWS Glue provider compatibility
path identified by the provider spike. It does not implement the AWS storage or
Glue catalog plugins. It prepares the account, IAM, cost controls, IaC, and
agent workflow needed to run those tests once the provider implementation
exists.

## Current Context

Floe already has a remote validation lane based on DevPod plus Hetzner. That
lane remains the control path for heavyweight contributor validation. The
provider compatibility spike recommends AWS S3 plus AWS Glue as the first
native cloud provider proof, with Nessie plus MinIO as a fallback when AWS
access is unavailable.

The current repository has no AWS DevPod target and no repo-owned AWS
OpenTofu scaffold for provider testing. Existing AWS references are mostly
architecture docs, provider-matrix docs, and future plugin references.

## Principles

- Keep provider contracts composable: capabilities, requirements, typed
  bindings, and resolver validation own cross-plugin compatibility.
- Keep `CompiledArtifacts` secret-free.
- Keep Helm/renderers and runtime code consuming resolved deployment bindings,
  not rediscovering AWS config.
- Prefer temporary or scoped credentials over long-lived access keys.
- Make AWS setup repeatable through OpenTofu, not console instructions.
- Make cleanup evidence mandatory for every live run.
- Keep the default cost profile close to zero when no validation is running.
- Separate product failures, provider failures, infrastructure failures, and
  cleanup failures in all runbooks.

## Recommended Approach

Use a repo-owned OpenTofu scaffold plus a short human guide and a reusable
Codex skill.

The human guide explains only what a person must prepare before an agent can
act: an AWS account, budget recipient, admin or bootstrap credentials, region
choice, and any organization-specific guardrails. The OpenTofu scaffold owns
test bucket, IAM, budgets, lifecycle policy, and outputs. The Codex skill owns
the repeatable agent procedure for applying, validating, using, and destroying
the environment.

This is stronger than a guide-only design because it avoids copy/paste drift.
It is smaller than a full AWS platform migration because EKS, NAT Gateways,
Glue jobs, crawlers, and long-running EC2 are not required for the first
provider proof.

## Deliverables

### 1. Human Setup Guide

Path:

- `docs/contributing/aws-provider-testing.md`

The guide should cover:

- Purpose of the AWS test account.
- Required human-owned prerequisites:
  - AWS account or sandbox account available for destructive testing.
  - Permission to create IAM roles, S3 buckets, Glue databases, and Budgets.
  - Approved AWS region.
  - Budget alert email address.
  - Local AWS CLI authentication path for the agent, such as SSO profile or
    administrator bootstrap profile.
  - Confirmation that no production or customer data will be used.
- What the agent will create with OpenTofu.
- What the agent must never create by default.
- How contributors hand an AWS profile and variables to the agent.
- How to verify the account is clean after a run.

The guide should not be a long manual console walkthrough. Its job is to make
the human-agent handoff clear and safe.

### 2. OpenTofu Scaffold

Path:

- `infra/aws-provider-tests/`

The scaffold should create the minimum AWS resources needed for live provider
tests:

- Reusable S3 test bucket.
- Public access block for the bucket.
- Server-side encryption for the bucket.
- Lifecycle rule for `runs/` prefixes.
- Abort-incomplete-multipart-upload lifecycle rule.
- IAM role or policy for provider tests with scoped S3 and Glue access.
- Optional IAM user/access key only if a role-assumption flow is not practical;
  this should be disabled by default.
- AWS Budget with a low configurable monthly threshold.
- Common resource tags.
- Outputs for bucket name, region, role ARN, run-prefix convention, Glue
  database prefix, and recommended environment variables.

The scaffold should not create:

- EKS clusters.
- NAT Gateways.
- Always-on EC2 instances.
- Glue jobs or crawlers.
- Lake Formation resources.
- S3 Tables resources.
- Production deployment resources.
- Repository-stored secrets.

### 3. AWS DevPod Target

The first implementation should leave AWS DevPod as an optional extension, not
the default provider-test requirement.

When added, it should provide:

- `.devcontainer/aws/devcontainer.json`.
- Make/script configuration that can select `DEVPOD_PROVIDER=aws`.
- Configurable instance type, disk size, region, and tags.
- Workspace deletion after validation.
- Direct AWS inventory evidence for EC2 instances, volumes, security groups, and
  any provider-created SSH keys.

AWS DevPod plus Kind is useful for network locality and EC2 instance-profile
testing. It is not a substitute for EKS Pod Identity or IRSA validation.

### 4. Reusable Codex Skill

Path:

- `.codex/skills/floe-aws-provider-testing/`

The skill should be concise and procedural. It should trigger when an agent is
asked to set up, validate, run, or clean up the Floe AWS provider testing
environment.

The skill should include:

- `SKILL.md` with the core workflow.
- Optional scripts or references only when they prevent fragile repetition.
- A strict preflight checklist:
  - Confirm repository path and branch.
  - Confirm AWS account ID and region.
  - Confirm the OpenTofu working directory.
  - Confirm no production resources are targeted.
  - Confirm budget and cleanup expectations.
- Apply workflow:
  - `tofu init`.
  - `tofu plan`.
  - Review resource classes and cost-sensitive resources.
  - `tofu apply` only when authorized.
- Validation workflow:
  - `aws sts get-caller-identity`.
  - S3 bucket and prefix checks.
  - Glue database/table permissions checks.
  - Secret scan for generated local artifacts.
- Cleanup workflow:
  - Delete current-run Glue databases and tables.
  - Empty current-run S3 prefixes.
  - Run `tofu destroy` when the test account scaffold is no longer needed.
  - Re-inventory AWS resources after cleanup.
- Failure classification:
  - Product failure.
  - Provider failure.
  - Infrastructure failure.
  - Cleanup failure.

The skill should not contain account-specific IDs, credentials, or long
provider documentation. Detailed AWS reference material should remain in the
repo guide or linked official docs.

## Configuration Model

The OpenTofu scaffold should be driven by explicit variables:

- `aws_region`
- `name_prefix`
- `owner`
- `budget_email`
- `monthly_budget_limit_usd`
- `s3_bucket_name`
- `s3_run_prefix`
- `glue_database_prefix`
- `enable_access_key_user`
- `enable_aws_devpod_permissions`
- `common_tags`

Default values should be safe:

- Low monthly budget.
- Short lifecycle retention for `runs/`.
- AWS DevPod permissions disabled.
- Access-key user disabled.
- No production-like names.

The guide should show a minimal `terraform.tfvars` example and a local-only
override file pattern. No generated state or secret material should be committed.

## Runtime Data Flow

1. Human creates or selects the AWS sandbox account and authentication method.
2. Agent runs OpenTofu from `infra/aws-provider-tests/`.
3. OpenTofu emits the provider-test bucket, IAM role or policy, budget, tags,
   and environment-variable hints.
4. Agent exports the generated AWS test configuration.
5. Floe provider validation creates per-run S3 prefixes and Glue databases.
6. Validation captures resolver, binding, runtime translation, live read/write,
   and secret-scan evidence.
7. Cleanup removes current-run resources and verifies no current-run AWS
   resources remain.

No AWS credentials flow through `CompiledArtifacts`.

## Evidence Required

Static evidence:

- `tofu fmt -check`
- `tofu validate`
- `tofu plan` showing only expected resource classes
- Markdown docs validation
- Secret scan over guide, IaC, skill, and generated examples

AWS readiness evidence:

- AWS caller identity and account ID match the approved sandbox.
- S3 bucket exists with public access blocked.
- S3 lifecycle rule covers `runs/`.
- Glue read/create/delete permissions work against the test database prefix.
- Budget exists with the configured alert email.
- IAM policy scope is limited to test resources.

Live run evidence:

- Unique run ID.
- Resolved provider-test environment variables.
- Compiled artifact secret scan.
- Runtime catalog/storage config derived from typed bindings.
- Live S3 write/read/delete result.
- Live Glue database/table create/list/drop result.
- Post-run S3 and Glue cleanup inventory.

AWS DevPod evidence, when enabled:

- DevPod provider and workspace identity.
- EC2 instance type, region, tags, and deletion result.
- Direct AWS inventory after cleanup for instances, volumes, and security
  groups matching the run prefix.

## Cost Controls

The default path should incur only negligible ongoing cost:

- S3 storage only for temporary test artifacts.
- Glue Data Catalog metadata only during test runs.
- Budget alert always present.
- Lifecycle rules remove stale `runs/` data.
- No NAT Gateway.
- No EKS.
- No always-on EC2.
- No Glue jobs or crawlers.

Any optional AWS DevPod run must delete its workspace after validation and
perform direct AWS inventory before declaring cleanup complete.

## Out Of Scope

- Implementing `floe-storage-aws-s3`.
- Implementing `floe-catalog-glue`.
- Migrating Floe product deployment to AWS.
- Adding EKS, IRSA, or EKS Pod Identity validation.
- Adding Lake Formation or S3 Tables validation.
- Replacing the existing Hetzner DevPod lane.
- Storing AWS secrets in the repository.
- Running live AWS validation without explicit account and cleanup approval.

## Approval Criteria

This design is ready for implementation planning when the approved plan covers:

- OpenTofu scaffold tasks.
- Human guide tasks.
- Codex skill tasks.
- Validation tasks for docs, OpenTofu, secret scanning, and AWS readiness.
- Cleanup tasks that directly inventory AWS resources after every live run.
