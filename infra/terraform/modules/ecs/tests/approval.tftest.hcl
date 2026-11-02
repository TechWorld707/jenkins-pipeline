mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"ecs-tasks.amazonaws.com\"},\"Action\":\"sts:AssumeRole\"}]}"
    }
  }
}

variables {
  name               = "webtech-test"
  subnet_ids         = ["subnet-12345678"]
  security_group_ids = { frontend = "sg-12345678", backend = "sg-12345678" }
  db_host            = "database.example.invalid"
  db_name            = "webtech"
  db_secret_arn      = "arn:aws:secretsmanager:eu-west-2:671662643382:secret:test-secret"
  desired_count      = 2
  max_task_count     = 6
  retention_days     = 14
  target_group_arn   = "arn:aws:elasticloadbalancing:eu-west-2:671662643382:targetgroup/test/1234567890123456"
  container_insights = false
}

run "infrastructure_cannot_launch_application" {
  command = plan

  assert {
    condition     = aws_ecs_service.frontend.desired_count == 0 && aws_ecs_service.backend.desired_count == 0
    error_message = "Fresh services must remain idle until Jenkins approval."
  }
  assert {
    condition     = alltrue([for target in aws_appautoscaling_target.service : target.min_capacity == 0 && target.suspended_state[0].dynamic_scaling_in_suspended && target.suspended_state[0].dynamic_scaling_out_suspended && target.suspended_state[0].scheduled_scaling_suspended])
    error_message = "Scaling must not wake unapproved application services."
  }
  assert {
    condition     = alltrue([for target in aws_appautoscaling_target.service : target.tags.ReleaseMinCapacity == "2" && target.max_capacity == 6])
    error_message = "Jenkins must be able to read the approved runtime capacity bounds."
  }
  assert {
    condition     = alltrue([for task in aws_ecs_task_definition.app : jsondecode(task.container_definitions)[0].image == "example.invalid/awaiting-jenkins-approval:unreleased"])
    error_message = "Terraform must not select application release images."
  }
}

run "production_collector_preserves_manual_launch_boundary" {
  command = plan
  variables {
    name = "webtech-production"
    production_telemetry = {
      metrics_url     = "https://metrics.example.invalid/api/v1/write"
      tempo_url       = "https://tempo.example.invalid"
      auth_secret_arn = "arn:aws:secretsmanager:eu-west-2:671662643382:secret:test-telemetry"
      collector_image = "example.invalid/collector:test"
    }
  }
  assert {
    condition = (
      aws_ecs_service.backend.desired_count == 0 &&
      aws_ecs_service.frontend.desired_count == 0 &&
      length(jsondecode(aws_ecs_task_definition.app["backend"].container_definitions)) == 2 &&
      jsondecode(aws_ecs_task_definition.app["backend"].container_definitions)[1].essential == false
    )
    error_message = "Adding production telemetry must not launch services or make collector availability essential."
  }
}

run "staging_does_not_acquire_collector" {
  command = plan
  variables {
    name = "webtech-staging"
  }
  assert {
    condition     = length(jsondecode(aws_ecs_task_definition.app["backend"].container_definitions)) == 1 && length(aws_ssm_parameter.telemetry_templates) == 0
    error_message = "Staging must retain its single application container without production templates."
  }
}
