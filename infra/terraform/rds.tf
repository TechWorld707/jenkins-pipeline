resource "aws_db_subnet_group" "main" {
  name       = "webtech-db-subnets"
  subnet_ids = aws_subnet.data[*].id

  tags = {
    Name = "webtech-db-subnets"
  }
}

resource "aws_db_instance" "postgres" {
  identifier           = "webtech-postgres-db"
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
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az               = true

  storage_encrypted          = true
  backup_retention_period    = 7
  auto_minor_version_upgrade = true

  skip_final_snapshot                   = true
  deletion_protection                   = true
  copy_tags_to_snapshot                 = true
  iam_database_authentication_enabled   = true
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.application_logs.arn
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]

  depends_on = [aws_iam_role_policy_attachment.rds_monitoring, aws_cloudwatch_log_group.rds]

  tags = {
    Name = "webtech-postgres-db"
  }
}

resource "aws_iam_role_policy" "ecs_db_secret" {
  name = "webtech-db-secret-access"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = aws_db_instance.postgres.master_user_secret[0].secret_arn
    }]
  })
}

output "postgres_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "postgres_secret_arn" {
  value = aws_db_instance.postgres.master_user_secret[0].secret_arn
}
resource "aws_db_parameter_group" "postgres" {
  name_prefix = "webtech-postgres18-"
  family      = "postgres18"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  parameter {
    name  = "log_statement"
    value = "all"
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
  name = "webtech-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:rds:eu-west-2:${data.aws_caller_identity.current.account_id}:db:webtech-postgres-db" }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_cloudwatch_log_group" "rds" {
  for_each          = toset(["postgresql", "upgrade"])
  name              = "/aws/rds/instance/webtech-postgres-db/${each.key}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.application_logs.arn
}
