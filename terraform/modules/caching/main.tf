# ElastiCache subnet group
resource "aws_elasticache_subnet_group" "nlp_cache_subnet_group" {
  name = "${var.environment_name}-nlp-cache-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "${var.environment_name}-nlp-cache-subnet-group"
    Environment = var.environment_name
  }
}

resource "aws_elasticache_parameter_group" "nlp_cache_params" {
  family = "redis7"
  name   = "${var.environment_name}-nlp-cache-redis-params"

  parameter {
    name  = "maxmemory-policy"
    value = "noeviction"
  }

  tags = {
    Name        = "${var.environment_name}-nlp-cache-redis-params"
    Environment = var.environment_name
  }
}

# CloudWatch log group for Redis
resource "aws_cloudwatch_log_group" "nlp-cache-logs" {
  name              = "/redis/${var.environment_name}-nlp-cache-logs"
  retention_in_days = 7

  tags = {
    Name        = "${var.environment_name}-nlp-redis-logs"
    Environment = var.environment_name
  }
}

resource "aws_security_group" "nlp-redis-sg" {
  name = "${var.environment_name}-nlp-cache-sg"
  description = "Security group for nlp redis"

  vpc_id = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"

    cidr_blocks = [var.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment_name}-nlp-cache"
    Environment = var.environment_name
  }
}

# ElastiCache Redis replication group
resource "aws_elasticache_replication_group" "nlp_cache_cluster" {
  replication_group_id = "${var.environment_name}-nlp-cache"
  description          = "Cache cluster for ${var.environment_name} nlp"

  node_type            =  "cache.t3.small"
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.nlp_cache_params.name

engine               = "redis"
  engine_version       = "7.0"

  num_cache_clusters   = var.redis_num_cache_nodes
  subnet_group_name    = aws_elasticache_subnet_group.nlp_cache_subnet_group.name

  security_group_ids = [aws_security_group.nlp-redis-sg.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  auth_token                 = random_password.nlp_cache_redis_password.result

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.nlp-cache-logs.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  tags = {
    Name        = "${var.environment_name}-nlp-cache"
    Environment = var.environment_name
  }
} 
