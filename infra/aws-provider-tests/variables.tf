variable "aws_region" {
  description = "AWS region for low-cost provider compatibility resources."
  type        = string
  default     = "ap-southeast-2"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be a valid AWS region identifier such as ap-southeast-2."
  }
}

variable "name_prefix" {
  description = "Lowercase prefix used for named AWS resources."
  type        = string
  default     = "floe-provider-tests"

  validation {
    condition     = can(regex("^[a-z0-9]+(-[a-z0-9]+)*$", var.name_prefix))
    error_message = "name_prefix must contain only lowercase letters, numbers, and single hyphens."
  }
}

variable "owner" {
  description = "Human owner for tags and budget traceability."
  type        = string

  validation {
    condition     = length(trimspace(var.owner)) > 0
    error_message = "owner is required."
  }
}

variable "budget_email" {
  description = "Email address that receives AWS Budget notifications."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.budget_email))
    error_message = "budget_email must be a valid email address."
  }
}

variable "monthly_budget_limit_usd" {
  description = "Monthly AWS Budget limit in USD."
  type        = number
  default     = 25

  validation {
    condition     = var.monthly_budget_limit_usd > 0 && var.monthly_budget_limit_usd <= 100
    error_message = "monthly_budget_limit_usd must be greater than 0 and less than or equal to 100."
  }
}

variable "s3_bucket_name" {
  description = "Optional explicit S3 bucket name. Defaults to a deterministic account and region qualified name."
  type        = string
  default     = null

  validation {
    condition = var.s3_bucket_name == null || can(regex(
      "^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$",
      var.s3_bucket_name,
    ))
    error_message = "s3_bucket_name must be null or a valid lowercase S3 bucket name."
  }
}

variable "s3_run_prefix" {
  description = "Relative S3 prefix used for provider test run data."
  type        = string
  default     = "runs/"

  validation {
    condition = can(regex("^[^/][A-Za-z0-9!_.*'()/-]*/$", var.s3_run_prefix)) && (
      !startswith(var.s3_run_prefix, "/")
    )
    error_message = "s3_run_prefix must be a relative prefix ending with a slash."
  }
}

variable "run_data_retention_days" {
  description = "Number of days to retain provider test run objects."
  type        = number
  default     = 3

  validation {
    condition     = var.run_data_retention_days >= 1 && var.run_data_retention_days <= 30
    error_message = "run_data_retention_days must be between 1 and 30."
  }
}

variable "glue_database_prefix" {
  description = "Prefix for temporary Glue databases created by provider tests."
  type        = string
  default     = "floe_provider_"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]*_$", var.glue_database_prefix))
    error_message = "glue_database_prefix must be lowercase snake_case and end with an underscore."
  }
}

variable "enable_access_key_user" {
  description = "Whether to create an IAM user for manually managed provider test credentials. No access keys are created."
  type        = bool
  default     = false
}

variable "enable_aws_devpod_permissions" {
  description = "Whether to include read-only EC2 inventory permissions needed by AWS DevPod workflows."
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Additional tags merged into all taggable resources."
  type        = map(string)
  default     = {}
}
