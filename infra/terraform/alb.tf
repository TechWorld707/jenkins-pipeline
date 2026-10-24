# Public entry point for the website; internet accessibility is intentional.
# trivy:ignore:AVD-AWS-0053
resource "aws_lb" "frontend" {
  name               = "webtech-frontend-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = false
  drop_invalid_header_fields = true

  tags = {
    Name = "webtech-frontend-alb"
  }
}

resource "aws_lb_target_group" "frontend" {
  # checkov:skip=CKV_AWS_378:Learning environment intentionally uses HTTP; private frontend access is restricted by security groups.
  name        = "webtech-frontend-tg"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    path                = "/"
    protocol            = "HTTP"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Name = "webtech-frontend-tg"
  }
}

# Learning environment uses the ALB DNS name without a domain or TLS certificate.
# trivy:ignore:AVD-AWS-0054
resource "aws_lb_listener" "http" {
  # checkov:skip=CKV_AWS_2:Learning environment intentionally serves HTTP without a domain or certificate.
  # checkov:skip=CKV_AWS_103:TLS policy does not apply to this intentional HTTP-only learning listener.
  load_balancer_arn = aws_lb.frontend.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

output "alb_origin_dns_name" {
  description = "Public ALB DNS name for the website"
  value       = aws_lb.frontend.dns_name
}
