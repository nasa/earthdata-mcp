# Store database credentials in Secrets Manager
resource "aws_secretsmanager_secret" "database" {
  name        = "${var.environment_name}-earthdata-mcp-db"
  description = "PostgreSQL credentials for earthdata-mcp database"

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-db-secret"
  })
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id

  secret_string = jsonencode({
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    database = aws_db_instance.main.db_name
    username = aws_db_instance.main.username
    password = random_password.master.result
    # Connection string for convenience
    url = "postgresql://${aws_db_instance.main.username}:${random_password.master.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}"
  })
}
