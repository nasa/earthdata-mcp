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

# Application infrastructure
module "application" {
  source = "../modules/application"

  environment_name = var.environment_name
  vpc_id           = data.aws_vpc.main.id
  subnet_ids       = data.aws_subnets.main.ids

  # Configuration
  cmr_url            = var.cmr_url
  associations_table = var.associations_table

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
