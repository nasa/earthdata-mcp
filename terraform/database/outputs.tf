output "db_instance_id" {
  description = "RDS instance ID"
  value       = module.database.db_instance_id
}

output "db_instance_endpoint" {
  description = "RDS instance endpoint"
  value       = module.database.db_instance_endpoint
}

output "db_instance_address" {
  description = "RDS instance address (hostname)"
  value       = module.database.db_instance_address
}

output "db_instance_port" {
  description = "RDS instance port"
  value       = module.database.db_instance_port
}

output "db_name" {
  description = "Database name"
  value       = module.database.db_name
}

output "security_group_id" {
  description = "Security group ID for the database"
  value       = module.database.security_group_id
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = module.database.secret_arn
}

output "secret_name" {
  description = "Name of the Secrets Manager secret"
  value       = module.database.secret_name
}
