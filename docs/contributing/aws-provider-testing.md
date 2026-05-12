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

~~~text
Set up the Floe AWS provider testing environment from /Users/dmccarthy/Projects/floe.
Use AWS profile <profile-name>, region <region>, owner <owner>, and budget email <email>.
Use OpenTofu under infra/aws-provider-tests.
Do not create EKS, NAT Gateway, Glue jobs, Glue crawlers, Lake Formation, S3 Tables, or always-on EC2.
Run readiness checks and report the AWS account ID, region, bucket, Glue database prefix, and cleanup status.
~~~

## Clean Account Check

After exporting the OpenTofu `recommended_environment` outputs and setting the
current `FLOE_PROVIDER_SPIKE_RUN`, ask the agent to verify:

```bash
aws sts get-caller-identity
FLOE_PROVIDER_SPIKE_RUN=floe-provider-YYYYMMDDTHHMMSSZ scripts/aws-provider-test-cleanup.sh
```

The final report must say whether current-run S3 prefixes and Glue databases
were removed.
