# IAM policy for Secrets Manager access
resource "aws_iam_policy" "ecs_secrets_manager" {
  name        = "${var.environment_name}-langfuse-ecs-secrets-manager"
  description = "Policy for ECS tasks to access Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.database_url.arn,
          aws_secretsmanager_secret.redis_connection.arn,
          aws_secretsmanager_secret.clickhouse_password.arn,
          aws_secretsmanager_secret.nextauth_secret.arn,
          aws_secretsmanager_secret.encryption_key.arn,
          aws_secretsmanager_secret.salt.arn
        ]
      }
    ]
  })

  tags = {
    Name        = "${var.environment_name}-langfuse-ecs-secrets-manager"
    Environment = var.environment_name
  }
}

# Attach the policy to the ECS execution role
resource "aws_iam_role_policy_attachment" "ecs_execution_secrets_manager" {
  policy_arn = aws_iam_policy.ecs_secrets_manager.arn
  role       = aws_iam_role.ecs_execution_role.name
}

