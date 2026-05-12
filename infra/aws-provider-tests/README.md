# AWS Provider Test Account Scaffold

This OpenTofu scaffold prepares low-cost AWS resources for Floe provider compatibility validation. It creates S3, IAM, and Budget resources only.

It does not create EKS, EC2, NAT Gateways, Glue jobs, Glue crawlers, Lake Formation, or S3 Tables.

Before using this scaffold, read the human prerequisite guidance in `docs/contributing/aws-provider-testing.md`.

## Agent Workflow

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
