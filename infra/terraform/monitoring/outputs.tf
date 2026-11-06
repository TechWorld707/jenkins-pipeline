output "instance_id" { value = aws_instance.host.id }
output "data_volume_id" { value = aws_ebs_volume.data.id }
output "credentials_secret_arn" { value = aws_secretsmanager_secret.credentials.arn }
output "production_telemetry" {
  description = "Set PRODUCTION_TELEMETRY_JSON after successful host bootstrap; values are not secrets."
  value = {
    metrics_url      = "https://${aws_network_interface.host.private_ip}/api/v1/write"
    tempo_url        = "https://${aws_network_interface.host.private_ip}"
    auth_secret_arn  = aws_secretsmanager_secret.credentials.arn
    use_private_ca   = true
    auth_kms_key_arn = aws_kms_key.storage.arn
  }
}
output "grafana_tunnel" {
  value = "aws ssm start-session --region eu-west-2 --target ${aws_instance.host.id} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"3000\"],\"localPortNumber\":[\"13000\"]}'"
}
