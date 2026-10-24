resource "aws_db_subnet_group" "main" {
  name       = "webtech-db-subnets"
  subnet_ids = aws_subnet.data[*].id

  tags = {
    Name = "webtech-db-subnets"
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = "webtech-postgres-db"
  engine         = "postgres"
  instance_class = "db.t3.micro"

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp3"
  db_name               = "webtech"
  username              = "webtech_admin"

  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az               = false

  storage_encrypted          = true
  backup_retention_period    = 1
  auto_minor_version_upgrade = true

  skip_final_snapshot = true

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