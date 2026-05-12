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
