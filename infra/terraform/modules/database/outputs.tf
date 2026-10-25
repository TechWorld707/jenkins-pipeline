output "host" { value = aws_db_instance.postgres.address }
output "name" { value = aws_db_instance.postgres.db_name }
output "secret_arn" { value = aws_db_instance.postgres.master_user_secret[0].secret_arn }
