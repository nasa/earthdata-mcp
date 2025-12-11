# ECR Repository for Langfuse Web
resource "aws_ecr_repository" "langfuse_web" {
  name                 = "langfuse-web-${var.environment_name}"
  
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "langfuse-web-${var.environment_name}"
    Environment = var.environment_name
  }
}

resource "aws_ecr_lifecycle_policy" "langfuse_web_ecr_lifecycle" {
  repository = aws_ecr_repository.langfuse_web.name
  policy = <<EOF
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep only 5 most recent images",
      "selection": {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 5
      },
      "action": {
        "type": "expire"
      }
    }
  ]
}
EOF
}

# ECR Repository for Langfuse Worker
resource "aws_ecr_repository" "langfuse_worker" {
  name                 = "langfuse-worker-${var.environment_name}"
  
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "langfuse-worker-${var.environment_name}"
    Environment = var.environment_name
  }
}

resource "aws_ecr_lifecycle_policy" "langfuse_worker_ecr_lifecycle" {
  repository = aws_ecr_repository.langfuse_worker.name
  policy = <<EOF
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep only 5 most recent images",
      "selection": {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 5
      },
      "action": {
        "type": "expire"
      }
    }
  ]
}
EOF
}