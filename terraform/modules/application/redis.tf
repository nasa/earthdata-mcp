# Redis for application caching (KMS terms, geocoding, search)

# Random password for Redis auth
resource "random_password" "redis_password" {
  length      = 64
  special     = false
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

# Store Redis credentials in Secrets Manager
resource "aws_secretsmanager_secret" "redis" {
  name        = "${var.environment_name}-earthdata-mcp-redis"
  description = "Redis credentials for earthdata-mcp caching"

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-redis-secret"
  })
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id

  secret_string = jsonencode({
    host     = aws_elasticache_replication_group.redis.primary_endpoint_address
    port     = aws_elasticache_replication_group.redis.port
    password = random_password.redis_password.result
    ssl      = true
  })
}

# Security group for Redis
resource "aws_security_group" "redis" {
  name        = "${var.environment_name}-earthdata-mcp-redis"
  description = "Security group for earthdata-mcp Redis cache"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-redis"
  })
}

# Ingress rules as standalone resources so each service manages its own access


resource "aws_security_group_rule" "redis_from_mcp" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.mcp_server.id
  security_group_id        = aws_security_group.redis.id
  description              = "Redis from MCP server"
}

# ElastiCache subnet group
resource "aws_elasticache_subnet_group" "redis" {
  name        = "${var.environment_name}-earthdata-mcp-redis"
  description = "Subnet group for earthdata-mcp Redis"
  subnet_ids  = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-redis"
  })
}

# ElastiCache parameter group
resource "aws_elasticache_parameter_group" "redis" {
  family      = "redis7"
  name        = "${var.environment_name}-earthdata-mcp-redis"
  description = "Parameter group for earthdata-mcp Redis"

  # Allow eviction when memory is full (appropriate for caching)
  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-redis"
  })
}

# ElastiCache replication group (single node for cost efficiency)
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${var.environment_name}-earthdata-mcp-application"
  description                = "Redis cache for earthdata-mcp (KMS, geocoding, search)"
  node_type                  = var.redis_node_type
  port                       = 6379
  parameter_group_name       = aws_elasticache_parameter_group.redis.name
  automatic_failover_enabled = false
  num_cache_clusters         = 1
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  engine                     = "redis"
  engine_version             = "7.0"
  auth_token                 = random_password.redis_password.result
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-redis"
  })
}
