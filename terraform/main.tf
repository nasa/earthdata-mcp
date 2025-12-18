# ECR repositories 
module "ecr" {
  source = "./modules/ecr"
  environment_name = var.environment_name
}

# NLP Caching infrastructure
module "caching" {
  source = "./modules/caching"

  environment_name = var.environment_name
  vpc_id          = data.aws_vpc.app.id
  vpc_cidr_block  = data.aws_vpc.app.cidr_block
  subnet_ids      = data.aws_subnets.app.ids
  
  # Redis configuration
  redis_num_cache_nodes = var.redis_num_cache_nodes
}

# Langfuse infrastructure (depends on ECR)
module "langfuse" {
  source = "./modules/langfuse"
  
  environment_name = var.environment_name
  vpc_id           = data.aws_vpc.app.id
  vpc_cidr_block   = data.aws_vpc.app.cidr_block
  subnet_ids       = data.aws_subnets.app.ids
  
  lb_listener = data.aws_lb_listener.cmr_lb_listener.arn
  load_balancer_dns = data.aws_lb.cmr_lb.dns_name
  
  # Use ECR outputs
  langfuse_web_image = "${module.ecr.langfuse_web_repository_url}:latest"
  langfuse_worker_image = "${module.ecr.langfuse_worker_repository_url}:latest"
  
  # Redis configuration
  redis_node_type       = "cache.t3.small"
  redis_num_cache_nodes = 1
  redis_at_rest_encryption = true
  
  # ClickHouse configuration
  clickhouse_cpu    = 2048
  clickhouse_memory = 4096
  
  # ECS configuration
  web_cpu          = 2048
  web_memory       = 4096
  worker_cpu       = 2048
  worker_memory    = 4096
  web_desired_count = 1
  worker_desired_count = 1
  
  # Region for resources
  aws_region = var.aws_region
}
