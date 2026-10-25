resource "aws_codebuild_project" "image_builder" {
  # checkov:skip=CKV_AWS_316:Docker builds and Trivy container scans require Docker daemon access; privileged mode is limited to this image-builder project.
  name          = "webtech-shared-image-builder"
  description   = "Builds, scans, and pushes WebTech frontend and backend images"
  service_role  = aws_iam_role.codebuild_image_builder.arn
  build_timeout = 30

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
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
      value = aws_s3_bucket.reports.id
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
    Name = "webtech-shared-image-builder"
  }
}

output "codebuild_image_builder_project_name" {
  value = aws_codebuild_project.image_builder.name
}
