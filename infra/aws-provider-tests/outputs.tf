output "aws_account_id" {
  description = "AWS account ID used by this provider test scaffold."
  value       = local.account_id
}

output "aws_region" {
  description = "AWS region used by this provider test scaffold."
  value       = var.aws_region
}

output "s3_bucket_name" {
  description = "S3 bucket for provider compatibility test run data."
  value       = aws_s3_bucket.provider_tests.bucket
}

output "s3_run_prefix" {
  description = "S3 prefix for provider compatibility test run data."
  value       = var.s3_run_prefix
}

output "glue_database_prefix" {
  description = "Glue database prefix permitted for provider compatibility tests."
  value       = var.glue_database_prefix
}

output "provider_test_policy_arn" {
  description = "IAM policy ARN containing provider compatibility test permissions."
  value       = aws_iam_policy.provider_test_permissions.arn
}

output "budget_name" {
  description = "AWS Budget name used for provider compatibility test cost controls."
  value       = aws_budgets_budget.provider_tests.name
}

output "budget_email" {
  description = "AWS Budget subscriber email used for provider compatibility test cost alerts."
  value       = var.budget_email
  sensitive   = true
}

output "recommended_environment" {
  description = "Environment variables recommended for Floe AWS provider compatibility tests."
  value = {
    FLOE_AWS_REGION                   = var.aws_region
    FLOE_AWS_TEST_BUCKET              = aws_s3_bucket.provider_tests.bucket
    FLOE_AWS_TEST_PREFIX              = var.s3_run_prefix
    FLOE_AWS_GLUE_DATABASE_PREFIX     = var.glue_database_prefix
    FLOE_AWS_BUDGET_NAME              = aws_budgets_budget.provider_tests.name
    FLOE_AWS_BUDGET_EMAIL             = var.budget_email
    FLOE_AWS_PROVIDER_TEST_POLICY_ARN = aws_iam_policy.provider_test_permissions.arn
  }
  sensitive = true
}
