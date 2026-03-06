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
  force_delete         = false

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
  force_delete         = false

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

resource "aws_ecr_repository" "enrichment_lambda" {
  name                 = "${var.environment_name}-earthdata-mcp-enrichment"
  image_tag_mutability = "MUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-enrichment"
  })
}

resource "aws_ecr_lifecycle_policy" "enrichment_lambda" {
  repository = aws_ecr_repository.enrichment_lambda.name

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
  force_delete         = false

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

# ECR Repository for MCP server
resource "aws_ecr_repository" "mcp_server" {
  name                 = "${var.environment_name}-earthdata-mcp-server"
  image_tag_mutability = "MUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-server"
  })
}

resource "aws_ecr_lifecycle_policy" "mcp_server" {
  repository = aws_ecr_repository.mcp_server.name

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

# Application infrastructure (Lambdas, SQS, SNS subscription, MCP server)
module "application" {
  source = "../modules/application"

  environment_name = var.environment_name
  vpc_id           = data.aws_vpc.main.id
  subnet_ids       = data.aws_subnets.main.ids

  # SNS subscription
  cmr_sns_topic_arn = local.cmr_sns_topic_arn

  # Database (from remote state)
  database_secret_arn              = data.terraform_remote_state.database.outputs.secret_arn
  database_security_group_id       = data.terraform_remote_state.database.outputs.security_group_id
  database_proxy_endpoint          = data.terraform_remote_state.database.outputs.proxy_endpoint
  database_proxy_security_group_id = data.terraform_remote_state.database.outputs.proxy_security_group_id

  # Lambda container images
  ingest_lambda_image    = "${aws_ecr_repository.ingest_lambda.repository_url}:${var.image_tag}"
  embedding_lambda_image = "${aws_ecr_repository.embedding_lambda.repository_url}:${var.image_tag}"
  bootstrap_lambda_image   = "${aws_ecr_repository.bootstrap_lambda.repository_url}:${var.image_tag}"
  enrichment_lambda_image  = "${aws_ecr_repository.enrichment_lambda.repository_url}:${var.image_tag}"

  # Configuration
  cmr_url            = var.cmr_url
  embeddings_table   = var.embeddings_table
  associations_table = var.associations_table

  # Lambda configuration
  ingest_lambda_timeout        = var.ingest_lambda_timeout
  ingest_lambda_memory         = var.ingest_lambda_memory
  ingest_lambda_concurrency    = var.ingest_lambda_concurrency
  embedding_lambda_timeout     = var.embedding_lambda_timeout
  embedding_lambda_memory      = var.embedding_lambda_memory
  embedding_lambda_concurrency   = var.embedding_lambda_concurrency
  enrichment_lambda_concurrency  = var.enrichment_lambda_concurrency
  bootstrap_lambda_concurrency   = var.bootstrap_lambda_concurrency
  bootstrap_lambda_timeout       = var.bootstrap_lambda_timeout
  bootstrap_lambda_memory      = var.bootstrap_lambda_memory

  # Langfuse
  langfuse_host       = var.langfuse_host
  langfuse_public_key = var.langfuse_public_key

  # MCP Server
  load_balancer_name       = var.load_balancer_name
  mcp_server_image         = "${aws_ecr_repository.mcp_server.repository_url}:${var.image_tag}"
  mcp_server_cpu           = var.mcp_server_cpu
  mcp_server_memory        = var.mcp_server_memory
  mcp_server_desired_count = var.mcp_server_desired_count
  mcp_server_min_count     = var.mcp_server_min_count
  mcp_server_max_count     = var.mcp_server_max_count
  mcp_listener_priority    = var.mcp_listener_priority

  # Geocode Index (OpenSearch)
  geocode_index_host   = var.geocode_index_host
  geocode_index_region = var.geocode_index_region
  geocode_index_port   = var.geocode_index_port

  # Geometry simplification
  simplify_geom_max_point = var.simplify_geom_max_point

  # Granule validation
  granule_validation_max_workers = var.granule_validation_max_workers

  # Tool associations
  tool_assoc_max_workers = var.tool_assoc_max_workers

  tags = var.tags
}

# Allow embedding lambda to connect to database (direct)
resource "aws_security_group_rule" "lambda_to_database" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.application.embedding_lambda_security_group_id
  security_group_id        = data.terraform_remote_state.database.outputs.security_group_id
  description              = "PostgreSQL from embedding lambda"
}

# Allow enrichment lambda to connect to database (direct)
resource "aws_security_group_rule" "enrichment_to_database" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.application.enrichment_lambda_security_group_id
  security_group_id        = data.terraform_remote_state.database.outputs.security_group_id
  description              = "PostgreSQL from enrichment lambda"
}

# Allow MCP server to connect to database (direct)
resource "aws_security_group_rule" "mcp_server_to_database" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.application.mcp_server_security_group_id
  security_group_id        = data.terraform_remote_state.database.outputs.security_group_id
  description              = "PostgreSQL from MCP server"
}

# Allow embedding lambda to connect to RDS Proxy
resource "aws_security_group_rule" "lambda_to_proxy" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.application.embedding_lambda_security_group_id
  security_group_id        = data.terraform_remote_state.database.outputs.proxy_security_group_id
  description              = "PostgreSQL from embedding lambda"
}

# Allow enrichment lambda to connect to RDS Proxy
resource "aws_security_group_rule" "enrichment_to_proxy" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.application.enrichment_lambda_security_group_id
  security_group_id        = data.terraform_remote_state.database.outputs.proxy_security_group_id
  description              = "PostgreSQL from enrichment lambda"
}

# Allow MCP server to connect to RDS Proxy
resource "aws_security_group_rule" "mcp_server_to_proxy" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.application.mcp_server_security_group_id
  security_group_id        = data.terraform_remote_state.database.outputs.proxy_security_group_id
  description              = "PostgreSQL from MCP server"
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
