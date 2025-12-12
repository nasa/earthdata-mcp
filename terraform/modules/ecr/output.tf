output "langfuse_web_repository_url" {
  description = "URL of the Langfuse web ECR repository"
  value       = aws_ecr_repository.langfuse_web.repository_url
}

output "langfuse_worker_repository_url" {
  description = "URL of the Langfuse worker ECR repository"
  value       = aws_ecr_repository.langfuse_worker.repository_url
}
