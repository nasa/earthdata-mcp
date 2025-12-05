# Redis outputs
output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.redis.port
}

output "redis_auth_token" {
  description = "Redis auth token"
  value       = random_password.redis_password.result
  sensitive   = true
}

# PostgreSQL outputs
output "postgres_endpoint" {
  description = "PostgreSQL cluster endpoint"
  value       = aws_rds_cluster.postgres.endpoint
}

output "postgres_reader_endpoint" {
  description = "PostgreSQL cluster reader endpoint"
  value       = aws_rds_cluster.postgres.reader_endpoint
}

output "postgres_port" {
  description = "PostgreSQL port"
  value       = aws_rds_cluster.postgres.port
}

output "postgres_database_name" {
  description = "PostgreSQL database name"
  value       = aws_rds_cluster.postgres.database_name
}

output "postgres_username" {
  description = "PostgreSQL master username"
  value       = aws_rds_cluster.postgres.master_username
}

output "postgres_password" {
  description = "PostgreSQL master password"
  value       = random_password.postgres_password.result
  sensitive   = true
}

# S3 outputs
output "s3_bucket_name" {
  description = "S3 bucket name for Langfuse storage"
  value       = aws_s3_bucket.langfuse.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.langfuse.arn
}
