# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data sources for VPC and subnets
data "aws_vpc" "main" {
  filter {
    name   = "tag:Name"
    values = [var.vpc_tag_name_filter]
  }
}

data "aws_subnets" "main" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }

  tags = {
    Name = var.subnet_tag_name_filter
  }
}

# Cross-stack reference to database via remote state
data "terraform_remote_state" "database" {
  backend = "s3"
  config = {
    bucket = "tf-state-cmr-${var.environment_name}"
    key    = "earthdata-mcp/database-${var.environment_name}"
    region = var.aws_region
  }
}

locals {
  cmr_sns_topic_arn = "arn:aws:sns:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.cmr_sns_topic_name}"
}

# ECR Repositories for Lambda functions
resource "aws_ecr_repository" "ingest_lambda" {
  name                 = "${var.environment_name}-earthdata-mcp-ingest"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-ingest"
  })
}

resource "aws_ecr_lifecycle_policy" "ingest_lambda" {
  repository = aws_ecr_repository.ingest_lambda.name

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

resource "aws_ecr_repository" "embedding_lambda" {
  name                 = "${var.environment_name}-earthdata-mcp-embedding"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-embedding"
  })
}

resource "aws_ecr_lifecycle_policy" "embedding_lambda" {
  repository = aws_ecr_repository.embedding_lambda.name

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

resource "aws_ecr_repository" "bootstrap_lambda" {
  name                 = "${var.environment_name}-earthdata-mcp-bootstrap"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-bootstrap"
  })
}

resource "aws_ecr_lifecycle_policy" "bootstrap_lambda" {
  repository = aws_ecr_repository.bootstrap_lambda.name

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

# Application infrastructure (Lambdas, SQS, SNS subscription)
module "application" {
  source = "../modules/application"

  environment_name = var.environment_name
  vpc_id           = data.aws_vpc.main.id
  subnet_ids       = data.aws_subnets.main.ids

  # SNS subscription
  cmr_sns_topic_arn = local.cmr_sns_topic_arn

  # Database (from remote state)
  database_secret_arn        = data.terraform_remote_state.database.outputs.secret_arn
  database_security_group_id = data.terraform_remote_state.database.outputs.security_group_id

  # Lambda container images
  ingest_lambda_image    = "${aws_ecr_repository.ingest_lambda.repository_url}:${var.image_tag}"
  embedding_lambda_image = "${aws_ecr_repository.embedding_lambda.repository_url}:${var.image_tag}"
  bootstrap_lambda_image = "${aws_ecr_repository.bootstrap_lambda.repository_url}:${var.image_tag}"

  # Configuration
  cmr_url                = var.cmr_url
  embeddings_table       = var.embeddings_table
  associations_table     = var.associations_table
  kms_embeddings_table   = var.kms_embeddings_table
  kms_associations_table = var.kms_associations_table
  embedding_model        = var.embedding_model
  bedrock_region         = var.bedrock_region

  # Lambda configuration
  ingest_lambda_timeout        = var.ingest_lambda_timeout
  ingest_lambda_memory         = var.ingest_lambda_memory
  ingest_lambda_concurrency    = var.ingest_lambda_concurrency
  embedding_lambda_timeout     = var.embedding_lambda_timeout
  embedding_lambda_memory      = var.embedding_lambda_memory
  embedding_lambda_concurrency = var.embedding_lambda_concurrency
  bootstrap_lambda_timeout     = var.bootstrap_lambda_timeout
  bootstrap_lambda_memory      = var.bootstrap_lambda_memory

  # Langfuse
  langfuse_host       = var.langfuse_host
  langfuse_public_key = var.langfuse_public_key
  langfuse_secret_key = var.langfuse_secret_key

  tags = var.tags
}

# Allow embedding lambda to connect to database
resource "aws_security_group_rule" "lambda_to_database" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.application.embedding_lambda_security_group_id
  security_group_id        = data.terraform_remote_state.database.outputs.security_group_id
  description              = "PostgreSQL from embedding lambda"
}

# SSM Parameters for cross-stack references (queue URLs)
resource "aws_ssm_parameter" "ingest_queue_url" {
  name        = "${var.environment_name}-ingest-queue-url"
  description = "URL of the ingest SQS queue"
  type        = "String"
  value       = module.application.ingest_queue_url

  tags = var.tags
}

resource "aws_ssm_parameter" "embedding_queue_url" {
  name        = "${var.environment_name}-embedding-queue-url"
  description = "URL of the embedding FIFO queue"
  type        = "String"
  value       = module.application.embedding_queue_url

  tags = var.tags
}
