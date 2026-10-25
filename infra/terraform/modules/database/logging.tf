resource "aws_kms_key" "logs" {
  description             = "${var.name} database logs"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }, Action = "kms:*", Resource = "*" },
      {
        Effect    = "Allow"
        Principal = { Service = "logs.eu-west-2.amazonaws.com" }
        Action    = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"]
        Resource  = "*"
        Condition = { ArnLike = { "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:eu-west-2:${data.aws_caller_identity.current.account_id}:log-group:/aws/rds/instance/${var.name}-postgres/*" } }
      }
    ]
  })
}
