data "aws_ec2_managed_prefix_list" "cloudfront" { name = "com.amazonaws.global.cloudfront.origin-facing" }
resource "aws_security_group" "app" {
  # checkov:skip=CKV2_AWS_5:Groups attach to ALB/RDS/ECS through module inputs; ECS indexes the frontend/backend group map.
  for_each    = toset(["alb", "frontend", "backend", "database"])
  name        = "${local.name}-${each.key}"
  description = "${local.name} ${each.key} access"
  vpc_id      = module.network.vpc_id
}
resource "aws_vpc_security_group_ingress_rule" "alb" {
  # checkov:skip=CKV_AWS_260:Port 80 is restricted to the AWS CloudFront origin-facing managed prefix list; no public CIDR ingress is allowed.
  security_group_id = aws_security_group.app["alb"].id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  description       = "CloudFront origin access"
}
locals {
  connections = {
    frontend = { source = "alb", destination = "frontend", port = 8080 }
    backend  = { source = "frontend", destination = "backend", port = 8000 }
    database = { source = "backend", destination = "database", port = 5432 }
  }
}
resource "aws_vpc_security_group_ingress_rule" "internal" {
  for_each                     = local.connections
  security_group_id            = aws_security_group.app[each.value.destination].id
  referenced_security_group_id = aws_security_group.app[each.value.source].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
  description                  = "Application tier access"
}
resource "aws_vpc_security_group_egress_rule" "internal" {
  for_each                     = local.connections
  security_group_id            = aws_security_group.app[each.value.source].id
  referenced_security_group_id = aws_security_group.app[each.value.destination].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
  description                  = "Application tier access"
}
# Private tasks need HTTPS to public ECR, Secrets Manager and CloudWatch APIs via NAT.
# trivy:ignore:AVD-AWS-0104
resource "aws_vpc_security_group_egress_rule" "https" {
  for_each          = toset(["frontend", "backend"])
  security_group_id = aws_security_group.app[each.key].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "AWS APIs and image pulls through NAT"
}
