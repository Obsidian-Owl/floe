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
  limit_amount = var.monthly_budget_limit_usd
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
