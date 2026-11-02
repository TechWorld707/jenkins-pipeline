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
output "observability" {
  value = {
    alert_topic_arn       = module.observability.production_alert_topic_arn
    dashboard_name        = "webtech-production-observability"
    runtime_alarm_actions = var.monitoring_runtime_expected
    collector_configured  = var.production_telemetry != null
    alb_suffix            = module.ingress.alb_arn_suffix
    target_group_suffix   = module.ingress.target_group_arn_suffix
  }
}
