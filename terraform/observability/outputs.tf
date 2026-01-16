# Langfuse outputs
output "langfuse_host" {
  description = "Langfuse host URL"
  value       = module.langfuse.langfuse_host
}

output "langfuse_api_keys_secret_arn" {
  description = "ARN of the Langfuse API keys secret"
  value       = aws_secretsmanager_secret.langfuse_api_keys.arn
}

# ECR outputs
output "langfuse_web_repository_url" {
  description = "ECR repository URL for Langfuse web"
  value       = module.langfuse.langfuse_web_repository_url
}

output "langfuse_worker_repository_url" {
  description = "ECR repository URL for Langfuse worker"
  value       = module.langfuse.langfuse_worker_repository_url
}

# Langfuse Redis outputs
output "langfuse_redis_endpoint" {
  description = "Langfuse Redis endpoint"
  value       = module.langfuse.redis_endpoint
}

# Langfuse PostgreSQL outputs
output "langfuse_postgres_endpoint" {
  description = "Langfuse PostgreSQL endpoint"
  value       = module.langfuse.postgres_endpoint
}

# S3 outputs
output "langfuse_s3_bucket_name" {
  description = "Langfuse S3 bucket name"
  value       = module.langfuse.s3_bucket_name
}
