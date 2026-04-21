output "endpoint" {
  description = "RDS endpoint in host:port format."
  value       = "${aws_db_instance.main.address}:${aws_db_instance.main.port}"
  sensitive   = true
}

output "address" {
  description = "RDS hostname."
  value       = aws_db_instance.main.address
  sensitive   = true
}

output "port" {
  description = "RDS port."
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "Database name."
  value       = aws_db_instance.main.db_name
}

output "master_user_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the master password (managed by RDS)."
  value       = aws_db_instance.main.master_user_secret[0].secret_arn
  sensitive   = true
}
