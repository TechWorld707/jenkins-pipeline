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
  name               = "webtech-codebuild-image-builder"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume_role.json
}

resource "aws_cloudwatch_log_group" "codebuild_image_builder" {
  name              = "/aws/codebuild/webtech-image-builder"
  retention_in_days = 365
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
    resources = ["${aws_s3_bucket.alb_logs.arn}/reports/*"]
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
  name   = "webtech-codebuild-ecr-and-logs"
  role   = aws_iam_role.codebuild_image_builder.id
  policy = data.aws_iam_policy_document.codebuild_image_builder.json
}

resource "aws_codebuild_project" "image_builder" {
  # checkov:skip=CKV_AWS_316:Docker builds and Trivy container scans require Docker daemon access; privileged mode is limited to this image-builder project.
  name          = "webtech-image-builder"
  description   = "Builds, scans, and pushes WebTech frontend and backend images"
  service_role  = aws_iam_role.codebuild_image_builder.arn
  build_timeout = 30

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_MEDIUM"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = true

    environment_variable {
      name  = "AWS_ACCOUNT_ID"
      value = data.aws_caller_identity.current.account_id
    }

    environment_variable {
      name  = "SCAN_REPORT_BUCKET"
      value = aws_s3_bucket.alb_logs.id
    }

    environment_variable {
      name  = "FRONTEND_ECR_REPOSITORY"
      value = aws_ecr_repository.app["frontend"].name
    }

    environment_variable {
      name  = "BACKEND_ECR_REPOSITORY"
      value = aws_ecr_repository.app["backend"].name
    }
  }

  source {
    type            = "GITHUB"
    location        = "https://github.com/TechWorld707/jenkins-pipeline.git"
    buildspec       = "buildspec.yml"
    git_clone_depth = 1
  }

  source_version = "main"

  depends_on = [aws_iam_role_policy.codebuild_image_builder]

  logs_config {
    cloudwatch_logs {
      group_name  = aws_cloudwatch_log_group.codebuild_image_builder.name
      stream_name = "build"
    }
  }

  tags = {
    Name = "webtech-image-builder"
  }
}

output "codebuild_image_builder_project_name" {
  value = aws_codebuild_project.image_builder.name
}