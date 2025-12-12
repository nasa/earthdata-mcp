# Random password for Redis
resource "random_password" "nlp_cache_redis_password" {
  length      = 64
  special     = false
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

resource "aws_secretsmanager_secret" "nlp_cache_redis_password" {
  name = "${var.environment_name}-nlp-cache-password"
  description = "Redis authentication token for ${var.environment_name} environment"

  tags = {
    Name        = "${var.environment_name}-nlp-cache-redis-password"
    Environment = var.environment_name
  }
}

resource "aws_secretsmanager_secret_version" "nlp_cache_redis_password" {
  secret_id = aws_secretsmanager_secret.nlp_cache_redis_password.id
  secret_string = random_password.nlp_cache_redis_password.result
}
