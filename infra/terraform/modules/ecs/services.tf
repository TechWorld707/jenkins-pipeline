resource "aws_ecs_service" "backend" {
  name                               = "${var.name}-backend"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.app["backend"].arn
  desired_count                      = var.desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_ids["backend"]]
    assign_public_ip = false
  }
  service_connect_configuration {
    enabled   = true
    namespace = aws_service_discovery_http_namespace.main.arn
    service {
      port_name      = "backend"
      discovery_name = "backend"
      client_alias {
        dns_name = "backend"
        port     = 8000
      }
    }
  }

  # Jenkins owns application revisions; infrastructure applies preserve its release.
  lifecycle { ignore_changes = [task_definition] }
  depends_on = [aws_iam_role_policy_attachment.execution, aws_iam_role_policy.secrets]
}
resource "aws_ecs_service" "frontend" {
  name                               = "${var.name}-frontend"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.app["frontend"].arn
  desired_count                      = var.desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_ids["frontend"]]
    assign_public_ip = false
  }
  service_connect_configuration {
    enabled   = true
    namespace = aws_service_discovery_http_namespace.main.arn

  }
  health_check_grace_period_seconds = 120
  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "frontend"
    container_port   = 8080
  }
  # Jenkins owns application revisions; infrastructure applies preserve its release.
  lifecycle { ignore_changes = [task_definition] }
  depends_on = [aws_iam_role_policy_attachment.execution, aws_iam_role_policy.secrets, aws_ecs_service.backend]
}
