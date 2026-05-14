data "aws_iam_policy_document" "provider_test_permissions" {
  statement {
    sid = "ReadCallerIdentity"

    actions = [
      "sts:GetCallerIdentity",
    ]

    resources = ["*"]
  }

  statement {
    sid = "ReadProviderTestBucket"

    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.provider_tests.arn,
    ]
  }

  statement {
    sid = "ManageProviderTestRunObjects"

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
    sid = "ManageProviderTestGlueDatabases"

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
      "arn:aws:glue:${var.aws_region}:${local.account_id}:table/${var.glue_database_prefix}*/*",
    ]
  }

  statement {
    sid = "ManageProviderTestGlueTables"

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
      sid = "ReadAwsDevpodEc2Inventory"

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
  name   = "${var.name_prefix}-permissions"
  policy = data.aws_iam_policy_document.provider_test_permissions.json
}

resource "aws_iam_user" "provider_test" {
  count = var.enable_access_key_user ? 1 : 0

  name = "${var.name_prefix}-user"
}

resource "aws_iam_user_policy_attachment" "provider_test" {
  count = var.enable_access_key_user ? 1 : 0

  policy_arn = aws_iam_policy.provider_test_permissions.arn
  user       = aws_iam_user.provider_test[0].name
}
