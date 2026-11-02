resource "aws_sqs_queue" "event_failures" {
  for_each                  = local.event_patterns
  name                      = "${var.name}-${each.key}-telemetry-dlq"
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue_policy" "event_failures" {
  for_each  = local.event_patterns
  queue_url = aws_sqs_queue.event_failures[each.key].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Allow", Principal = { Service = "events.amazonaws.com" },
    Action    = "sqs:SendMessage", Resource = aws_sqs_queue.event_failures[each.key].arn,
    Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.production[each.key].arn } }
  }] })
}

resource "aws_cloudwatch_metric_alarm" "event_failures" {
  for_each            = local.event_patterns
  alarm_name          = "${var.name}-${each.key}-telemetry-delivery-failed"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.event_failures[each.key].name }
  statistic           = "Maximum"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  period              = 60
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.production_alerts[0].arn]
  ok_actions          = [aws_sns_topic.production_alerts[0].arn]
}
