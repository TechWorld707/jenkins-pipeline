variable "production_monitoring" {
  description = "Null preserves existing flow-log-only behaviour for other environments."
  type = object({
    alb_suffix          = string
    target_group_suffix = string
    database_id         = string
    nat_gateway_ids     = list(string)
    codebuild_project   = string
    runtime_expected    = bool
  })
  default = null
}

locals {
  production = var.production_monitoring != null && var.name == "webtech-production"
  # Availability alarms remain inactive until an approved release is expected to run.
  base_alarms = local.production ? {
    alb_5xx           = { namespace = "AWS/ApplicationELB", metric = "HTTPCode_ELB_5XX_Count", statistic = "Sum", threshold = 5, operator = "GreaterThanOrEqualToThreshold", dimensions = { LoadBalancer = var.production_monitoring.alb_suffix } }
    target_5xx        = { namespace = "AWS/ApplicationELB", metric = "HTTPCode_Target_5XX_Count", statistic = "Sum", threshold = 5, operator = "GreaterThanOrEqualToThreshold", dimensions = { LoadBalancer = var.production_monitoring.alb_suffix } }
    unhealthy_targets = { namespace = "AWS/ApplicationELB", metric = "UnHealthyHostCount", statistic = "Maximum", threshold = 1, operator = "GreaterThanOrEqualToThreshold", dimensions = { LoadBalancer = var.production_monitoring.alb_suffix, TargetGroup = var.production_monitoring.target_group_suffix } }
    db_cpu            = { namespace = "AWS/RDS", metric = "CPUUtilization", statistic = "Average", threshold = 85, operator = "GreaterThanOrEqualToThreshold", dimensions = { DBInstanceIdentifier = var.production_monitoring.database_id } }
    db_connections    = { namespace = "AWS/RDS", metric = "DatabaseConnections", statistic = "Maximum", threshold = 50, operator = "GreaterThanOrEqualToThreshold", dimensions = { DBInstanceIdentifier = var.production_monitoring.database_id } }
    db_memory         = { namespace = "AWS/RDS", metric = "FreeableMemory", statistic = "Minimum", threshold = 134217728, operator = "LessThanThreshold", dimensions = { DBInstanceIdentifier = var.production_monitoring.database_id } }
    db_storage        = { namespace = "AWS/RDS", metric = "FreeStorageSpace", statistic = "Minimum", threshold = 2147483648, operator = "LessThanThreshold", dimensions = { DBInstanceIdentifier = var.production_monitoring.database_id } }
    codebuild_failure = { namespace = "AWS/CodeBuild", metric = "FailedBuilds", statistic = "Sum", threshold = 1, operator = "GreaterThanOrEqualToThreshold", dimensions = { ProjectName = var.production_monitoring.codebuild_project } }
  } : {}
  nat_alarms = local.production ? { for index, id in var.production_monitoring.nat_gateway_ids : "nat_ports_${index}" => {
    namespace = "AWS/NATGateway", metric = "ErrorPortAllocation", statistic = "Sum", threshold = 1, operator = "GreaterThanOrEqualToThreshold", dimensions = { NatGatewayId = id }
  } } : {}
}

resource "aws_sns_topic" "production_alerts" {
  count             = local.production ? 1 : 0
  name              = "${var.name}-observability-alerts"
  kms_master_key_id = aws_kms_key.flow_logs.arn
}

resource "aws_cloudwatch_metric_alarm" "production" {
  # checkov:skip=CKV_AWS_319:Runtime notifications intentionally remain disabled for idle/unreleased services; enable through the reviewed runtime_expected input after manual release and validation.
  for_each            = merge(local.base_alarms, local.nat_alarms)
  alarm_name          = "${var.name}-${each.key}"
  alarm_description   = "Initial lab threshold; see docs/runbooks/production-observability.md."
  namespace           = each.value.namespace
  metric_name         = each.value.metric
  statistic           = each.value.statistic
  threshold           = each.value.threshold
  comparison_operator = each.value.operator
  dimensions          = each.value.dimensions
  period              = 60
  evaluation_periods  = each.key == "codebuild_failure" ? 1 : 2
  treat_missing_data  = "notBreaching"
  actions_enabled     = each.key == "codebuild_failure" ? true : var.production_monitoring.runtime_expected
  alarm_actions       = [aws_sns_topic.production_alerts[0].arn]
  ok_actions          = [aws_sns_topic.production_alerts[0].arn]
}

resource "aws_cloudwatch_log_group" "production_events" {
  # checkov:skip=CKV_AWS_338:Use the approved learning project's 30-day production retention rather than a one-year retention policy.
  for_each          = local.production ? toset(["ecs-events", "pipeline-events"]) : toset([])
  name              = "/webtech/production/${each.key}"
  retention_in_days = var.retention_days
  kms_key_id        = aws_kms_key.flow_logs.arn
}

locals {
  event_patterns = local.production ? {
    ecs = {
      group   = "ecs-events"
      pattern = { source = ["aws.ecs"], "detail-type" = ["ECS Task State Change", "ECS Deployment State Change", "ECS Service Action"], detail = { clusterArn = ["arn:aws:ecs:eu-west-2:${data.aws_caller_identity.current.account_id}:cluster/${var.name}"] } }
    }
    codebuild = {
      group   = "pipeline-events"
      pattern = { source = ["aws.codebuild"], "detail-type" = ["CodeBuild Build State Change"], detail = { "project-name" = [var.production_monitoring.codebuild_project] } }
    }
  } : {}
}

resource "aws_cloudwatch_event_rule" "production" {
  for_each      = local.event_patterns
  name          = "${var.name}-${each.key}-observability"
  event_pattern = jsonencode(each.value.pattern)
}

resource "aws_cloudwatch_event_target" "production_logs" {
  for_each = local.event_patterns
  rule     = aws_cloudwatch_event_rule.production[each.key].name
  arn      = aws_cloudwatch_log_group.production_events[each.value.group].arn
  dead_letter_config {
    arn = aws_sqs_queue.event_failures[each.key].arn
  }
  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 185
  }
  depends_on = [aws_cloudwatch_log_resource_policy.production_events, aws_sqs_queue_policy.event_failures]
}

resource "aws_cloudwatch_log_resource_policy" "production_events" {
  count       = local.production ? 1 : 0
  policy_name = "${var.name}-eventbridge-observability"
  policy_document = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Allow", Principal = { Service = ["events.amazonaws.com", "delivery.logs.amazonaws.com"] },
    Action    = ["logs:CreateLogStream", "logs:PutLogEvents"],
    Resource  = [for group in aws_cloudwatch_log_group.production_events : "${group.arn}:*"],
    Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id } }
  }] })
}

output "production_alert_topic_arn" {
  value = local.production ? aws_sns_topic.production_alerts[0].arn : null
}
