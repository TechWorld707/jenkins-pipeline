data "aws_caller_identity" "current" {}
resource "aws_db_subnet_group" "main" {
  name       = "${var.name}-db-subnets"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.name}-db-subnets"
  }
}

resource "aws_db_instance" "postgres" {
  # checkov:skip=CKV_AWS_157:Staging intentionally uses Single-AZ to reduce cost; production terraform.tfvars enables Multi-AZ.
  identifier           = "${var.name}-postgres"
  engine               = "postgres"
  engine_version       = "18.3"
  parameter_group_name = aws_db_parameter_group.postgres.name
  instance_class       = "db.t3.micro"

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp3"
  db_name               = "webtech"
  username              = "webtech_admin"

  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  multi_az               = var.multi_az

  storage_encrypted          = true
  backup_retention_period    = 1
  auto_minor_version_upgrade = true

  skip_final_snapshot                   = false
  final_snapshot_identifier             = "${var.name}-postgres-final"
  deletion_protection                   = var.deletion_protection
  copy_tags_to_snapshot                 = true
  iam_database_authentication_enabled   = true
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.logs.arn
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]

  depends_on = [aws_iam_role_policy_attachment.rds_monitoring, aws_cloudwatch_log_group.rds]

  tags = {
    Name = "${var.name}-postgres"
  }
}

resource "aws_db_parameter_group" "postgres" {
  name_prefix = "${var.name}-postgres18-"
  family      = "postgres18"
  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }
  parameter {
    name  = "log_statement"
    value = "none"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_iam_role" "rds_monitoring" {
  name = "${var.name}-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:rds:eu-west-2:${data.aws_caller_identity.current.account_id}:db:${var.name}-postgres" }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_cloudwatch_log_group" "rds" {
  # checkov:skip=CKV_AWS_338:Learning environments intentionally retain logs for 14-30 days; production retention must follow organisational requirements.
  for_each          = toset(["postgresql", "upgrade"])
  name              = "/aws/rds/instance/${var.name}-postgres/${each.key}"
  retention_in_days = var.retention_days
  kms_key_id        = aws_kms_key.logs.arn
}
