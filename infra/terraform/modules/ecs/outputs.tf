output "cluster_name" { value = aws_ecs_cluster.main.name }
output "frontend_service" { value = aws_ecs_service.frontend.name }
output "backend_service" { value = aws_ecs_service.backend.name }
output "execution_role_arn" { value = aws_iam_role.execution.arn }
output "task_role_arn" { value = aws_iam_role.task.arn }
