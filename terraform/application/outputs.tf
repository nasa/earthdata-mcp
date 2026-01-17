output "ingest_queue_arn" {
  description = "ARN of the ingest SQS queue"
  value       = module.application.ingest_queue_arn
}

output "ingest_queue_url" {
  description = "URL of the ingest SQS queue"
  value       = module.application.ingest_queue_url
}

output "ingest_dlq_arn" {
  description = "ARN of the ingest dead letter queue"
  value       = module.application.ingest_dlq_arn
}

output "embedding_queue_arn" {
  description = "ARN of the embedding FIFO queue"
  value       = module.application.embedding_queue_arn
}

output "embedding_queue_url" {
  description = "URL of the embedding FIFO queue"
  value       = module.application.embedding_queue_url
}

output "embedding_dlq_arn" {
  description = "ARN of the embedding dead letter queue"
  value       = module.application.embedding_dlq_arn
}

output "ingest_lambda_arn" {
  description = "ARN of the ingest Lambda function"
  value       = module.application.ingest_lambda_arn
}

output "ingest_lambda_name" {
  description = "Name of the ingest Lambda function"
  value       = module.application.ingest_lambda_name
}

output "embedding_lambda_arn" {
  description = "ARN of the embedding Lambda function"
  value       = module.application.embedding_lambda_arn
}

output "embedding_lambda_name" {
  description = "Name of the embedding Lambda function"
  value       = module.application.embedding_lambda_name
}

output "ingest_lambda_ecr_repository_url" {
  description = "ECR repository URL for ingest lambda"
  value       = aws_ecr_repository.ingest_lambda.repository_url
}

output "embedding_lambda_ecr_repository_url" {
  description = "ECR repository URL for embedding lambda"
  value       = aws_ecr_repository.embedding_lambda.repository_url
}

output "bootstrap_lambda_ecr_repository_url" {
  description = "ECR repository URL for bootstrap lambda"
  value       = aws_ecr_repository.bootstrap_lambda.repository_url
}
