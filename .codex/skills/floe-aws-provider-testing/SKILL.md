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
export FLOE_AWS_TEST_PREFIX=<s3-run-prefix>
export FLOE_AWS_GLUE_DATABASE_PREFIX=<glue-database-prefix>
export FLOE_AWS_BUDGET_NAME=<budget-name>
export FLOE_AWS_BUDGET_EMAIL=<budget-email>
export FLOE_AWS_PROVIDER_TEST_POLICY_ARN=<provider-test-policy-arn>
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
