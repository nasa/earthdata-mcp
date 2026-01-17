# ECR Repository for Langfuse Web
resource "aws_ecr_repository" "langfuse_web" {
  name                 = "${var.environment_name}-langfuse-web"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-web"
    Environment = var.environment_name
  }
}

resource "aws_ecr_lifecycle_policy" "langfuse_web" {
  repository = aws_ecr_repository.langfuse_web.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only 5 most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# ECR Repository for Langfuse Worker
resource "aws_ecr_repository" "langfuse_worker" {
  name                 = "${var.environment_name}-langfuse-worker"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-worker"
    Environment = var.environment_name
  }
}

resource "aws_ecr_lifecycle_policy" "langfuse_worker" {
  repository = aws_ecr_repository.langfuse_worker.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only 5 most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = {
        type = "expire"
      }
    }]
  })
}
