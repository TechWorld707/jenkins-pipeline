data "aws_subnet" "selected" { id = var.subnet_id }
data "aws_security_group" "backend" { id = var.backend_security_group_id }
data "aws_ssm_parameter" "ami" { name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64" }
data "aws_caller_identity" "current" {}
locals {
  name = "webtech-production-monitoring"
  # Reuse Grafana assets; EC2 has a Tempo 3 configuration, local fixtures retain Tempo 2.
  assets = merge(
    { for file in fileset("${path.module}/../../../observability/ec2/runtime", "**") : file => filebase64("${path.module}/../../../observability/ec2/runtime/${file}") },
    { "alerts.yml" = filebase64("${path.module}/../../../observability/alerts/production.yml"),
    "sync-annotations.py" = filebase64("${path.module}/../../../observability/sync-annotations.py") },
    { for file in fileset("${path.module}/../../../observability/grafana", "**") : "grafana/${file}" => filebase64("${path.module}/../../../observability/grafana/${file}") }
  )
}
resource "aws_security_group" "host" {
  name        = local.name
  description = "Private monitoring ingestion; administrative access uses SSM"
  vpc_id      = var.vpc_id
}
resource "aws_vpc_security_group_ingress_rule" "collector" {
  security_group_id            = aws_security_group.host.id
  referenced_security_group_id = var.backend_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "Production ECS collector HTTPS only"
}
resource "aws_vpc_security_group_egress_rule" "https" {
  security_group_id = aws_security_group.host.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
  description       = "Updates, image registries, AWS APIs through existing NAT"
}
resource "aws_network_interface" "host" {
  subnet_id       = var.subnet_id
  security_groups = [aws_security_group.host.id]
  tags            = { Name = local.name }
  lifecycle {
    precondition {
      condition     = data.aws_subnet.selected.vpc_id == var.vpc_id && data.aws_security_group.backend.vpc_id == var.vpc_id && !data.aws_subnet.selected.map_public_ip_on_launch
      error_message = "Select a private subnet and backend SG in the production VPC."
    }
  }
}
resource "aws_ebs_volume" "data" {
  availability_zone = data.aws_subnet.selected.availability_zone
  size              = 20
  type              = "gp3"
  encrypted         = true
  kms_key_id        = aws_kms_key.storage.arn
  tags              = { Name = "${local.name}-data" }
  lifecycle { prevent_destroy = true }
}
resource "aws_secretsmanager_secret" "credentials" {
  # checkov:skip=CKV2_AWS_57:Ingestion, nginx credential file, certificate trust and ECS secrets require coordinated manual rotation; see the EC2 runbook.
  kms_key_id              = aws_kms_key.storage.arn
  name                    = "${local.name}/credentials"
  description             = "Host-generated ingestion credentials, public TLS trust certificate, Grafana password; values stay outside Terraform state"
  recovery_window_in_days = 30
}
resource "aws_cloudwatch_log_group" "host" {
  # checkov:skip=CKV_AWS_338:Approved learning-project retention is 30 days; avoid a year of host logs.
  name              = "/webtech/production/monitoring-host"
  retention_in_days = 30
  kms_key_id        = var.log_kms_key_arn
}
resource "aws_iam_role" "host" {
  name               = local.name
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "host" {
  role = aws_iam_role.host.id
  policy = jsonencode({ Version = "2012-10-17", Statement = concat(jsondecode(file("${path.module}/../../../observability/permissions/grafana-cloudwatch.json")).Statement, [
    { Effect = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = "*", Condition = { StringEquals = { "cloudwatch:namespace" = "WebTech/MonitoringHost" } } },
    { Effect = "Allow", Action = ["ec2:DescribeTags", "ec2:DescribeVolumes"], Resource = "*" },
    { Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"], Resource = aws_kms_key.storage.arn },
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"], Resource = aws_secretsmanager_secret.credentials.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.host.arn}:*" }
  ]) })
}
resource "aws_iam_instance_profile" "host" {
  name = local.name
  role = aws_iam_role.host.name
}
resource "aws_instance" "host" {
  # checkov:skip=CKV_AWS_126:Use native five-minute metrics plus one-minute health probes; detailed EC2 monitoring adds cost without changing these five-minute alarms.
  ebs_optimized        = true
  ami                  = data.aws_ssm_parameter.ami.value
  instance_type        = var.instance_type
  iam_instance_profile = aws_iam_instance_profile.host.name
  network_interface {
    network_interface_id = aws_network_interface.host.id
    device_index         = 0
  }
  credit_specification { cpu_credits = "standard" }
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
    kms_key_id  = aws_kms_key.storage.arn
  }
  user_data_base64 = base64gzip(templatefile("${path.module}/bootstrap.sh.tftpl", {
    assets     = base64gzip(jsonencode(local.assets)), secret_arn = aws_secretsmanager_secret.credentials.arn,
    private_ip = aws_network_interface.host.private_ip, volume_id = aws_ebs_volume.data.id,
    images     = base64encode(jsonencode(var.images))
  }))
  user_data_replace_on_change = true
  tags                        = { Name = local.name }
  depends_on                  = [aws_iam_role_policy.host, aws_iam_role_policy_attachment.ssm]
}
resource "aws_volume_attachment" "data" {
  device_name                    = "/dev/sdf"
  stop_instance_before_detaching = true
  volume_id                      = aws_ebs_volume.data.id
  instance_id                    = aws_instance.host.id
}
resource "aws_cloudwatch_metric_alarm" "host" {
  for_each            = { status = { metric = "StatusCheckFailed", threshold = 1, statistic = "Maximum" }, cpu = { metric = "CPUUtilization", threshold = 85, statistic = "Average" } }
  alarm_name          = "${local.name}-${each.key}"
  namespace           = "AWS/EC2"
  metric_name         = each.value.metric
  statistic           = each.value.statistic
  threshold           = each.value.threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  period              = 300
  evaluation_periods  = 2
  treat_missing_data  = "breaching"
  dimensions          = { InstanceId = aws_instance.host.id }
  alarm_actions       = [var.alert_topic_arn]
  ok_actions          = [var.alert_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "disk" {
  alarm_name          = "${local.name}-disk"
  namespace           = "WebTech/MonitoringHost"
  metric_name         = "disk_used_percent"
  statistic           = "Maximum"
  threshold           = 80
  comparison_operator = "GreaterThanOrEqualToThreshold"
  period              = 300
  evaluation_periods  = 2
  treat_missing_data  = "breaching"
  dimensions          = { InstanceId = aws_instance.host.id, path = "/srv/webtech-observability", fstype = "ext4" }
  alarm_actions       = [var.alert_topic_arn]
  ok_actions          = [var.alert_topic_arn]
}
resource "aws_cloudwatch_metric_alarm" "readiness" {
  for_each            = { services = { metric = "ServiceHealthy", threshold = 1 }, certificate = { metric = "CertificateDaysRemaining", threshold = 30 } }
  alarm_name          = "${local.name}-${each.key}"
  namespace           = "WebTech/MonitoringHost"
  metric_name         = each.value.metric
  statistic           = "Minimum"
  threshold           = each.value.threshold
  comparison_operator = "LessThanThreshold"
  period              = 300
  evaluation_periods  = 2
  treat_missing_data  = "breaching"
  dimensions          = { InstanceId = aws_instance.host.id }
  alarm_actions       = [var.alert_topic_arn]
  ok_actions          = [var.alert_topic_arn]
}

resource "aws_kms_key" "storage" {
  description             = "Production monitoring EBS and credential encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid       = "AccountAdministration", Effect = "Allow",
    Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" },
    Action    = "kms:*", Resource = "*"
  }] })
}
