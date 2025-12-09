# Database URL Secret
resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.environment_name}-langfuse-database-url"
  
  tags = {
    Name        = "${var.environment_name}-langfuse-database-url"
    Environment = var.environment_name
  }
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql://${aws_rds_cluster.postgres.master_username}:${random_password.postgres_password.result}@${aws_rds_cluster.postgres.endpoint}:${aws_rds_cluster.postgres.port}/${aws_rds_cluster.postgres.database_name}"
}

# Redis Connection String Secret
resource "aws_secretsmanager_secret" "redis_connection" {
  name = "${var.environment_name}-langfuse-redis-connection"
  
  tags = {
    Name        = "${var.environment_name}-langfuse-redis-connection"
    Environment = var.environment_name
  }
}

resource "aws_secretsmanager_secret_version" "redis_connection" {
  secret_id = aws_secretsmanager_secret.redis_connection.id
  secret_string = "rediss://:${random_password.redis_password.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379"
}

# ClickHouse Password Secret
resource "aws_secretsmanager_secret" "clickhouse_password" {
  name = "${var.environment_name}-langfuse-clickhouse-password"
  
  tags = {
    Name        = "${var.environment_name}-langfuse-clickhouse-password"
    Environment = var.environment_name
  }
}

resource "aws_secretsmanager_secret_version" "clickhouse_password" {
  secret_id = aws_secretsmanager_secret.clickhouse_password.id
  secret_string = random_password.clickhouse_password.result
}

# NextAuth Secret
resource "aws_secretsmanager_secret" "nextauth_secret" {
  name = "${var.environment_name}-langfuse-nextauth-secret"
  
  tags = {
    Name        = "${var.environment_name}-langfuse-nextauth-secret"
    Environment = var.environment_name
  }
}

resource "aws_secretsmanager_secret_version" "nextauth_secret" {
  secret_id = aws_secretsmanager_secret.nextauth_secret.id
  secret_string = random_password.nextauth_secret.result
}

# Encryption Key Secret
resource "aws_secretsmanager_secret" "encryption_key" {
  name = "${var.environment_name}-langfuse-encryption-key"
  
  tags = {
    Name        = "${var.environment_name}-langfuse-encryption-key"
    Environment = var.environment_name
  }
}

resource "aws_secretsmanager_secret_version" "encryption_key" {
  secret_id = aws_secretsmanager_secret.encryption_key.id
  secret_string = random_id.encryption_key.hex
}

# Salt Secret
resource "aws_secretsmanager_secret" "salt" {
  name = "${var.environment_name}-langfuse-salt"
  
  tags = {
    Name        = "${var.environment_name}-langfuse-salt"
    Environment = var.environment_name
  }
}

resource "aws_secretsmanager_secret_version" "salt" {
  secret_id = aws_secretsmanager_secret.salt.id
  secret_string = random_password.langfuse_salt.result
}
