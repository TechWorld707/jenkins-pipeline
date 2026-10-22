resource "aws_ecs_cluster" "main" {
  name = "webtech-technologies"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "webtech-technologies"
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "webtech-technologies-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "webtech-technologies-ecs-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
