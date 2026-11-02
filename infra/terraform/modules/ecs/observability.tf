variable "production_telemetry" {
  description = "Production only. Full Authorization headers come from one Secrets Manager JSON secret."
  type = object({
    metrics_url     = string
    tempo_url       = string
    auth_secret_arn = string
    collector_image = optional(string, "ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-contrib@sha256:b6be1d9c10123821bebc952c62642abc36fe93c39c143faabc14e0e05065695a")
  })
  default = null
  validation {
    condition = var.production_telemetry == null ? true : (
      can(regex("^https://[A-Za-z0-9.-]+(:443)?(/[^?#@]*)?$", var.production_telemetry.metrics_url)) &&
      can(regex("^https://[A-Za-z0-9.-]+(:443)?(/[^?#@]*)?$", var.production_telemetry.tempo_url)) &&
      can(regex("^arn:aws:secretsmanager:eu-west-2:[0-9]{12}:secret:", var.production_telemetry.auth_secret_arn))
    )
    error_message = "Use HTTPS endpoints on port 443 without URL credentials/query/fragment, and a eu-west-2 Secrets Manager ARN."
  }
}

variable "telemetry_alert_topic_arn" {
  type        = string
  default     = null
  description = "Production SNS destination for collector export errors."
}

locals {
  telemetry_enabled = var.production_telemetry != null && var.name == "webtech-production"
  telemetry_environment = local.telemetry_enabled ? [
    { name = "OBSERVABILITY_ENABLED", value = "true" },
    { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://127.0.0.1:4318" },
    { name = "OTEL_TRACES_SAMPLER", value = "parentbased_traceidratio" },
    { name = "OTEL_TRACES_SAMPLER_ARG", value = "0.1" },
    { name = "DB_POOL_SIZE", value = "2" },
    { name = "DB_MAX_OVERFLOW", value = "0" },
    { name = "DB_POOL_TIMEOUT", value = "5" }
  ] : []
  collector = local.telemetry_enabled ? [{
    name      = "telemetry-collector"
    image     = var.production_telemetry.collector_image
    essential = false
    cpu       = 64
    memory    = 256
    command   = ["--config=env:OTEL_CONFIG"]
    environment = [
      { name = "OTEL_CONFIG", value = file("${path.module}/../../../../observability/collector/production.yaml") },
      { name = "METRICS_REMOTE_WRITE_URL", value = var.production_telemetry.metrics_url },
      { name = "TEMPO_OTLP_HTTP_URL", value = var.production_telemetry.tempo_url }
    ]
    secrets = [
      { name = "METRICS_AUTHORIZATION", valueFrom = "${var.production_telemetry.auth_secret_arn}:metrics_authorization::" },
      { name = "TEMPO_AUTHORIZATION", valueFrom = "${var.production_telemetry.auth_secret_arn}:tempo_authorization::" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.collector[0].name
        awslogs-region        = "eu-west-2"
        awslogs-stream-prefix = "collector"
      }
    }
  }] : []
}

resource "aws_cloudwatch_log_group" "collector" {
  # checkov:skip=CKV_AWS_338:Use the approved learning project's 30-day production retention rather than one year.
  count             = local.telemetry_enabled ? 1 : 0
  name              = "/webtech/production/telemetry-collector"
  retention_in_days = var.retention_days
  kms_key_id        = aws_kms_key.logs.arn
}

resource "aws_cloudwatch_log_metric_filter" "collector_error" {
  count          = local.telemetry_enabled ? 1 : 0
  name           = "${var.name}-collector-errors"
  log_group_name = aws_cloudwatch_log_group.collector[0].name
  pattern        = "{ $.level = \"error\" }"
  metric_transformation {
    name      = "CollectorExportError"
    namespace = "WebTech/Production"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "collector_error" {
  count               = local.telemetry_enabled ? 1 : 0
  alarm_name          = "${var.name}-collector-errors"
  namespace           = "WebTech/Production"
  metric_name         = "CollectorExportError"
  statistic           = "Sum"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  period              = 60
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.telemetry_alert_topic_arn == null ? [] : [var.telemetry_alert_topic_arn]
}

resource "aws_iam_role_policy" "telemetry_secret" {
  count = local.telemetry_enabled ? 1 : 0
  role  = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = var.production_telemetry.auth_secret_arn
  }] })
}

# Jenkins reads these exact Terraform-produced templates after manual approval.
# Terraform still does not update an active service's application revision.
resource "aws_ssm_parameter" "telemetry_templates" {
  # checkov:skip=CKV2_AWS_34:This String contains only non-secret task-definition ARNs; credentials and authorization headers stay in Secrets Manager.
  count = local.telemetry_enabled ? 1 : 0
  name  = "/webtech-production/observability/task-templates"
  type  = "String"
  value = jsonencode({ for name, definition in aws_ecs_task_definition.app : name => definition.arn })
}
