locals {
  scalable_services = {
    frontend = aws_ecs_service.frontend.name
    backend  = aws_ecs_service.backend.name
  }
  scaling_metrics = {
    cpu = {
      metric = "ECSServiceAverageCPUUtilization"
      target = 60
    }
    memory = {
      metric = "ECSServiceAverageMemoryUtilization"
      target = 70
    }
  }
  scaling_policies = {
    for pair in setproduct(keys(local.scalable_services), keys(local.scaling_metrics)) :
    "${pair[0]}-${pair[1]}" => {
      service = pair[0]
      metric  = local.scaling_metrics[pair[1]].metric
      target  = local.scaling_metrics[pair[1]].target
    }
  }
}

resource "aws_appautoscaling_target" "service" {
  for_each = local.scalable_services

  # Zero and suspended until Jenkins verifies the first approved release.
  min_capacity       = 0
  max_capacity       = var.max_task_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${each.value}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  tags = { ReleaseMinCapacity = tostring(var.desired_count) }

  suspended_state {
    dynamic_scaling_in_suspended  = true
    dynamic_scaling_out_suspended = true
    scheduled_scaling_suspended   = true
  }

  # Jenkins activates these after smoke tests; later applies preserve activation.
  lifecycle { ignore_changes = [min_capacity, suspended_state] }
}

resource "aws_appautoscaling_policy" "utilization" {
  for_each = local.scaling_policies

  name               = "${var.name}-${each.key}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.service[each.value.service].resource_id
  scalable_dimension = aws_appautoscaling_target.service[each.value.service].scalable_dimension
  service_namespace  = aws_appautoscaling_target.service[each.value.service].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = each.value.target
    scale_out_cooldown = 60
    scale_in_cooldown  = 300

    predefined_metric_specification {
      predefined_metric_type = each.value.metric
    }
  }
}
