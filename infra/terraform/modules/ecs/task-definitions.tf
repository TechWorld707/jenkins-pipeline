locals { ports = { frontend = 8080, backend = 8000 } }
resource "aws_cloudwatch_log_group" "app" {
  # checkov:skip=CKV_AWS_338:Learning environments intentionally retain logs for 14-30 days; production retention must follow organisational requirements.
  for_each          = local.ports
  name              = "/ecs/${var.name}/${each.key}"
  retention_in_days = var.retention_days
  kms_key_id        = aws_kms_key.logs.arn
}
resource "aws_ecs_task_definition" "app" {
  for_each                 = local.ports
  family                   = "${var.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name         = each.key
    image        = "example.invalid/awaiting-jenkins-approval:unreleased"
    essential    = true
    portMappings = [{ containerPort = each.value, hostPort = each.value, protocol = "tcp", name = each.key, appProtocol = "http" }]
    environment = each.key == "backend" ? [
      { name = "DB_HOST", value = var.db_host },
      { name = "DB_NAME", value = var.db_name },
      { name = "DB_SSLMODE", value = "require" }
    ] : []
    secrets = each.key == "backend" ? [
      { name = "DB_USER", valueFrom = "${var.db_secret_arn}:username::" },
      { name = "DB_PASSWORD", valueFrom = "${var.db_secret_arn}:password::" }
    ] : []
    logConfiguration = {
      logDriver = "awslogs"
      options   = { awslogs-group = aws_cloudwatch_log_group.app[each.key].name, awslogs-region = "eu-west-2", awslogs-stream-prefix = "ecs" }
    }
  }])
  depends_on = [aws_iam_role_policy_attachment.execution, aws_iam_role_policy.secrets]
}
