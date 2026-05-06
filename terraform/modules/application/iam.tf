# Get current AWS account ID
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# IAM role for ingest lambda




# IAM role for embedding lambda




# Security group for embedding lambda (VPC access to RDS)
resource "aws_security_group" "embedding_lambda" {
  name        = "${var.environment_name}-earthdata-mcp-embedding-sg"
  description = "Security group for embedding lambda VPC access"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-embedding-sg"
  })
}

# HTTPS egress for CMR, Bedrock, Secrets Manager
resource "aws_security_group_rule" "embedding_https_egress" {
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.embedding_lambda.id
  description       = "HTTPS outbound (CMR, Bedrock, Secrets Manager)"
}

# Allow embedding lambda to connect to database (direct)


# Allow embedding lambda to connect to RDS Proxy


# Allow embedding lambda to connect to Redis
resource "aws_security_group_rule" "embedding_to_redis" {
  type                     = "egress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.redis.id
  security_group_id        = aws_security_group.embedding_lambda.id
  description              = "Redis for caching"
}

# IAM role for bootstrap lambda
