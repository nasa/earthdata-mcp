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

# Load balancer data
data "aws_lb" "main" {
  name = var.load_balancer_name
}

data "aws_lb_listener" "https" {
  load_balancer_arn = data.aws_lb.main.arn
  port              = 443
}

# Langfuse infrastructure
module "langfuse" {
  source = "../modules/langfuse"

  environment_name = var.environment_name
  vpc_id           = data.aws_vpc.main.id
  vpc_cidr_block   = data.aws_vpc.main.cidr_block
  subnet_ids       = data.aws_subnets.main.ids
  aws_region       = var.aws_region

  # Load balancer
  lb_listener       = data.aws_lb_listener.https.arn
  load_balancer_dns = data.aws_lb.main.dns_name

  # Image tag and base path
  image_tag = var.image_tag
  base_path = var.base_path

  # Langfuse Redis configuration
  redis_node_type          = var.redis_node_type
  redis_num_cache_nodes    = 1
  redis_at_rest_encryption = true

  # Langfuse ClickHouse configuration
  clickhouse_cpu    = var.clickhouse_cpu
  clickhouse_memory = var.clickhouse_memory

  # Langfuse ECS configuration
  web_cpu              = var.web_cpu
  web_memory           = var.web_memory
  worker_cpu           = var.worker_cpu
  worker_memory        = var.worker_memory
  web_desired_count    = var.web_desired_count
  worker_desired_count = var.worker_desired_count
}

# Secret for Langfuse API keys (to be populated manually after Langfuse setup)
resource "aws_secretsmanager_secret" "langfuse_api_keys" {
  name        = "${var.environment_name}-langfuse-api-keys"
  description = "Langfuse API keys (populate after creating Langfuse project)"

  tags = merge(var.tags, {
    Name = "${var.environment_name}-langfuse-api-keys"
  })
}

resource "aws_secretsmanager_secret_version" "langfuse_api_keys" {
  secret_id = aws_secretsmanager_secret.langfuse_api_keys.id
  secret_string = jsonencode({
    public_key = "REPLACE_AFTER_LANGFUSE_SETUP"
    secret_key = "REPLACE_AFTER_LANGFUSE_SETUP"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# SSM Parameters for cross-stack references
resource "aws_ssm_parameter" "langfuse_host" {
  name        = "${var.environment_name}-langfuse-host"
  description = "Langfuse host URL"
  type        = "String"
  value       = module.langfuse.langfuse_host

  tags = var.tags
}

resource "aws_ssm_parameter" "langfuse_secret_arn" {
  name        = "${var.environment_name}-langfuse-secret-arn"
  description = "ARN of the Langfuse API keys secret"
  type        = "String"
  value       = aws_secretsmanager_secret.langfuse_api_keys.arn

  tags = var.tags
}
