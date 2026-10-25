output "jenkins_parameters" {
  value = {
    cluster          = module.ecs.cluster_name
    frontend_service = module.ecs.frontend_service
    backend_service  = module.ecs.backend_service
    url              = module.ingress.frontend_url
  }
}
output "execution_role_arn" { value = module.ecs.execution_role_arn }
output "task_role_arn" { value = module.ecs.task_role_arn }
