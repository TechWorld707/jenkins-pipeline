resource "aws_ecs_cluster" "main" {
  # checkov:skip=CKV_AWS_65:Container Insights is disabled for lean staging and enabled in the production module call.
  name = var.name
  setting {
    name  = "containerInsights"
    value = var.container_insights ? "enabled" : "disabled"
  }
}
resource "aws_service_discovery_http_namespace" "main" { name = var.name }
