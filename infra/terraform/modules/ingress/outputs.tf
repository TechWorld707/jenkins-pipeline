output "target_group_arn" { value = aws_lb_target_group.frontend.arn }
output "alb_arn_suffix" { value = aws_lb.frontend.arn_suffix }
output "target_group_arn_suffix" { value = aws_lb_target_group.frontend.arn_suffix }
