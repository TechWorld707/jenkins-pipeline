data "aws_iam_policy_document" "codebuild_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codebuild_image_builder" {
  name               = "webtech-shared-codebuild-image-builder"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume_role.json
}

resource "aws_cloudwatch_log_group" "codebuild_image_builder" {
  # checkov:skip=CKV_AWS_338:Learning environments intentionally retain logs for 14-30 days; production retention must follow organisational requirements.
  name              = "/aws/codebuild/webtech-shared-image-builder"
  retention_in_days = var.build_log_retention_days
  kms_key_id        = aws_kms_key.application_logs.arn
}

data "aws_iam_policy_document" "codebuild_image_builder" {
  statement {
    sid       = "WriteBuildLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.codebuild_image_builder.arn}:*"]
  }

  statement {
    sid       = "UploadPassingReports"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.reports.arn}/reports/*"]
  }

  statement {
    sid       = "GetECRLoginToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "PushFrontendAndBackendImages"
    effect = "Allow"

    actions = [
      "ecr:DescribeImages",
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart"
    ]

    resources = [
      aws_ecr_repository.app["frontend"].arn,
      aws_ecr_repository.app["backend"].arn
    ]
  }
}

resource "aws_iam_role_policy" "codebuild_image_builder" {
  name   = "webtech-shared-codebuild-ecr-and-logs"
  role   = aws_iam_role.codebuild_image_builder.id
  policy = data.aws_iam_policy_document.codebuild_image_builder.json
}
