# ECR Repository for Langfuse Web
resource "aws_ecr_repository" "langfuse_web" {
  name                 = "langfuse-web-${var.environment_name}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "langfuse-web-${var.environment_name}"
    Environment = var.environment_name
  }
}

# ECR Repository for Langfuse Worker
resource "aws_ecr_repository" "langfuse_worker" {
  name                 = "langfuse-worker-${var.environment_name}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "langfuse-worker-${var.environment_name}"
    Environment = var.environment_name
  }
}
