resource "aws_cloudwatch_log_metric_filter" "signals" {
  for_each = local.production ? {
    SyntheticSuccess         = "{ $.stage = \"production.synthetic\" && $.outcome = \"succeeded\" }"
    SyntheticFailure         = "{ $.stage = \"production.synthetic\" && $.outcome = \"failed\" }"
    DeploymentFailure        = "{ $.stage = \"production.deploy\" && $.outcome = \"failed\" }"
    ECSDeploymentFailure     = "{ $.detail.eventName = \"SERVICE_DEPLOYMENT_FAILED\" }"
    JenkinsObserverHeartbeat = "{ $.stage = \"production.observer.jenkins\" && $.outcome = \"succeeded\" }"
    GitHubObserverHeartbeat  = "{ $.stage = \"production.observer.github\" && $.outcome = \"succeeded\" }"
    PipelineRunOverdue       = "{ $.source = \"jenkins\" && $.outcome = \"overdue\" }"
  } : {}
  name           = "${var.name}-${each.key}"
  log_group_name = aws_cloudwatch_log_group.production_events[each.key == "ECSDeploymentFailure" ? "ecs-events" : "pipeline-events"].name
  pattern        = each.value
  metric_transformation {
    name      = each.key
    namespace = "WebTech/Production"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "signals" {
  # checkov:skip=CKV_AWS_319:Runtime notifications intentionally stay disabled until an approved production release and functioning probes/observers are verified.
  for_each            = local.production ? toset(["SyntheticSuccess", "SyntheticFailure", "DeploymentFailure", "ECSDeploymentFailure", "JenkinsObserverHeartbeat", "GitHubObserverHeartbeat", "PipelineRunOverdue"]) : toset([])
  alarm_name          = "${var.name}-${each.key}"
  namespace           = "WebTech/Production"
  metric_name         = each.key
  statistic           = "Sum"
  period              = contains(["SyntheticSuccess", "JenkinsObserverHeartbeat", "GitHubObserverHeartbeat"], each.key) ? 300 : 60
  threshold           = 1
  comparison_operator = contains(["SyntheticSuccess", "JenkinsObserverHeartbeat", "GitHubObserverHeartbeat"], each.key) ? "LessThanThreshold" : "GreaterThanOrEqualToThreshold"
  evaluation_periods  = each.key == "SyntheticFailure" ? 2 : 1
  treat_missing_data  = contains(["SyntheticSuccess", "JenkinsObserverHeartbeat", "GitHubObserverHeartbeat"], each.key) ? "breaching" : "notBreaching"
  actions_enabled     = var.production_monitoring.runtime_expected
  alarm_actions       = [aws_sns_topic.production_alerts[0].arn]
  ok_actions          = [aws_sns_topic.production_alerts[0].arn]
}

resource "aws_cloudwatch_dashboard" "production" {
  count          = local.production ? 1 : 0
  dashboard_name = "${var.name}-observability"
  dashboard_body = jsonencode({ widgets = [
    { type = "metric", x = 0, y = 0, width = 12, height = 6, properties = {
      title = "ALB errors and unhealthy targets", region = "eu-west-2", period = 60, view = "timeSeries",
      metrics = [
        ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", var.production_monitoring.alb_suffix, { stat = "Sum" }],
        ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.production_monitoring.alb_suffix, { stat = "Sum" }],
        ["AWS/ApplicationELB", "UnHealthyHostCount", "LoadBalancer", var.production_monitoring.alb_suffix, "TargetGroup", var.production_monitoring.target_group_suffix, { stat = "Maximum" }]
      ]
    } },
    { type = "metric", x = 12, y = 0, width = 12, height = 6, properties = {
      title = "RDS connections and CPU", region = "eu-west-2", period = 60, view = "timeSeries",
      metrics = [
        ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.production_monitoring.database_id],
        ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.production_monitoring.database_id]
      ]
    } },
    { type = "log", x = 0, y = 6, width = 24, height = 6, properties = {
      title = "Delivery evidence", region = "eu-west-2", view = "table",
      query = "SOURCE '/webtech/production/pipeline-events' | fields @timestamp, stage, outcome, commit_sha, codebuild_id | sort @timestamp desc | limit 100"
    } }
  ] })
}
