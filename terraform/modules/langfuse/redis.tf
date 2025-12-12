# Random password for Redis
resource "random_password" "redis_password" {
  length      = 64
  special     = false
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

resource "aws_security_group" "redis" {
  name = "langfuse-redis-${var.environment_name}"
  description = "Security group for Langfuse Redis"

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
    Name        = "${var.environment_name}-langfuse-redis"
    Environment = var.environment_name
  }
}

# ElastiCache parameter group
resource "aws_elasticache_parameter_group" "redis" {
  family = "redis7"
  name   = "${var.environment_name}-langfuse-redis-params"
  
  parameter {
    name  = "maxmemory-policy"
    value = "noeviction"
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-redis-params"
    Environment = var.environment_name
  }
}

# CloudWatch log group for Redis
resource "aws_cloudwatch_log_group" "redis" {
  name              = "/redis/${var.environment_name}-langfuse"
  retention_in_days = 7

  tags = {
    Name        = "${var.environment_name}-langfuse-redis-logs"
    Environment = var.environment_name
  }
}

# ElastiCache subnet group
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.environment_name}-langfuse-redis-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "${var.environment_name}-langfuse-redis-subnet-group"
    Environment = var.environment_name
  }
}

# ElastiCache replication group
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${var.environment_name}-langfuse"
  description                = "Redis cluster for Langfuse"
  node_type                  = var.redis_node_type
  port                       = 6379
  parameter_group_name       = aws_elasticache_parameter_group.redis.name
  automatic_failover_enabled = var.redis_num_cache_nodes > 1 ? true : false
  num_cache_clusters         = var.redis_num_cache_nodes
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  engine                     = "redis"
  engine_version             = "7.0"
  auth_token                 = random_password.redis_password.result
  transit_encryption_enabled = true
  at_rest_encryption_enabled = var.redis_at_rest_encryption
  
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  tags = {
    Name        = "${var.environment_name}-langfuse"
    Environment = var.environment_name
  }
}
