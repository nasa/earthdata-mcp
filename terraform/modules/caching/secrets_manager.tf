# Random password for Redis
resource "random_password" "redis_password" {
  length      = 64
  special     = false
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

resource "aws_secretsmanager_secret" "redis_password" {
  name = "${var.environment_name}-nlp-cache-redis-password"
  description = "Redis authentication token for ${var.environment_name} environment"

  tags = {
    Name        = "${var.environment_name}-nlp-cache-redis-password"
    Environment = var.environment_name
  }
}

resource "aws_secretsmanager_secret_version" "redis_password" {
  secret_id = aws_secretsmanager_secret.redis_password.id
  secret_string = random_password.redis_password.result
}
