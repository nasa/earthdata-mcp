# ECS Cluster
resource "random_password" "langfuse_salt" {
  length  = 64
  special = false
}

# Generate NextAuth secret
resource "random_id" "encryption_key" {
  byte_length = 32
}

resource "random_password" "nextauth_secret" {
  length  = 64
  special = true
}

resource "aws_ecs_cluster" "langfuse" {
  name = "${var.environment_name}-langfuse"

  tags = {
    Name        = "${var.environment_name}-langfuse"
    Environment = var.environment_name
  }
}

# Security Group for ECS tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.environment_name}-langfuse-ecs-tasks"
  description = "Security group for Langfuse ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr_block]
  }

  ingress {
    from_port   = 3030
    to_port     = 3030
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
    Name        = "${var.environment_name}-langfuse-ecs-tasks"
    Environment = var.environment_name
  }
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_execution_role" {
  name = "${var.environment_name}-langfuse-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.environment_name}-langfuse-ecs-execution-role"
    Environment = var.environment_name
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  role       = aws_iam_role.ecs_execution_role.name
}

# IAM Role for ECS Tasks
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.environment_name}-langfuse-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.environment_name}-langfuse-ecs-task-role"
    Environment = var.environment_name
  }
}

# Task Definition for Langfuse Web
resource "aws_ecs_task_definition" "langfuse_web" {
  family                   = "${var.environment_name}-langfuse-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.web_cpu
  memory                   = var.web_memory
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name  = "langfuse-web"
      image = var.langfuse_web_image
      portMappings = [
        {
          containerPort = 3000
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "REDIS_CONNECTION_STRING"
          value = "rediss://:${random_password.redis_password.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379"
        },
        {
          name  = "CLICKHOUSE_URL"
          value = "http://${var.environment_name}-langfuse-clickhouse.${var.environment_name}-langfuse.local:8123"
        },
        {
          name  = "CLICKHOUSE_MIGRATION_URL"
          value = "clickhouse://${var.environment_name}-langfuse-clickhouse.${var.environment_name}-langfuse.local:9000"
        },
        {
          name  = "ENCRYPTION_KEY"
          value = random_id.encryption_key.hex
        },
        {
          name  = "CLICKHOUSE_USER"
          value = "langfuse"
        },
        {
          name  = "CLICKHOUSE_CLUSTER_ENABLED"
          value = "false"
        },
        {
          name  = "NEXTAUTH_SECRET"
          value = random_password.nextauth_secret.result
        },
        {
          name  = "NEXT_PUBLIC_BASE_PATH"
          value = "/search/nlp/langfuse"
        },
        {
          name  = "NEXTAUTH_URL"
          value = "https://${var.load_balancer_dns}/search/nlp/langfuse/api/auth"
        },
        {
          name  = "SALT"
          value = random_password.langfuse_salt.result
        },
        {
          name  = "LANGFUSE_S3_EVENT_UPLOAD_BUCKET"
          value = aws_s3_bucket.langfuse.bucket
        },
        {
          name  = "LANGFUSE_S3_BATCH_EXPORT_BUCKET"
          value = aws_s3_bucket.langfuse.bucket
        },
        {
          name  = "LANGFUSE_S3_MEDIA_UPLOAD_BUCKET"
          value = aws_s3_bucket.langfuse.bucket
        },
        {
          name  = "TELEMETRY_ENABLED"
          value = "true"
        },
        {
          name  = "LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES"
          value = "true"
        },
        {
          name = "HOSTNAME",
          value = "0.0.0.0"
        }
      ]

      secrets = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_rds_cluster.postgres.master_username}:${random_password.postgres_password.result}@${aws_rds_cluster.postgres.endpoint}:${aws_rds_cluster.postgres.port}/${aws_rds_cluster.postgres.database_name}"
        },
        {
          name  = "CLICKHOUSE_PASSWORD"
          value = random_password.clickhouse_password.result
        },
        {
          name  = "NEXTAUTH_SECRET"
          value = random_password.nextauth_secret.result
        },
        {
          name  = "REDIS_CONNECTION_STRING"
          value = "rediss://:${random_password.redis_password.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379"
        },
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.langfuse_web.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      essential = true
    }
  ])
  

  tags = {
    Name        = "${var.environment_name}-langfuse-web"
    Environment = var.environment_name
  }
}

# Task Definition for Langfuse Worker
resource "aws_ecs_task_definition" "langfuse_worker" {
  family                   = "${var.environment_name}-langfuse-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      portMappings = [
        {
          containerPort = 3030
          protocol      = "tcp"
        }
      ]
      name  = "langfuse-worker"
      cpu       = 2048
      memory    = 4096
      essential = true
      
      image = var.langfuse_worker_image

      environment = [
        {
          name  = "TELEMETRY_ENABLED"
          value = "true"
        },
        {
          name  = "LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES"
          value = "true"
        },
        {
          name  = "CLICKHOUSE_URL"
          value = "http://${var.environment_name}-langfuse-clickhouse.${var.environment_name}-langfuse.local:8123"
        },
        {
          name  = "CLICKHOUSE_MIGRATION_URL"
          value = "clickhouse://${var.environment_name}-langfuse-clickhouse.${var.environment_name}-langfuse.local:9000"
        },
        {
          name  = "ENCRYPTION_KEY"
          value = random_id.encryption_key.hex
        },
        {
          name  = "CLICKHOUSE_USER"
          value = "langfuse"
        },
        {
          name  = "CLICKHOUSE_CLUSTER_ENABLED"
          value = "false"
        },
        {
          name  = "NEXT_PUBLIC_BASE_PATH"
          value = "/search/nlp/langfuse"
        },
        {
          name  = "NEXTAUTH_URL"
          value = "https://${var.load_balancer_dns}/search/nlp/langfuse/api/auth"
        },
        {
          name  = "SALT"
          value = random_password.langfuse_salt.result
        },
        {
          name  = "LANGFUSE_S3_EVENT_UPLOAD_BUCKET"
          value = aws_s3_bucket.langfuse.bucket
        },
        {
          name  = "LANGFUSE_S3_BATCH_EXPORT_BUCKET"
          value = aws_s3_bucket.langfuse.bucket
        },
        {
          name  = "LANGFUSE_S3_MEDIA_UPLOAD_BUCKET"
          value = aws_s3_bucket.langfuse.bucket
        },
        {
          name = "HOSTNAME",
          value = "0.0.0.0"
        }
      ],
      secrets = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_rds_cluster.postgres.master_username}:${random_password.postgres_password.result}@${aws_rds_cluster.postgres.endpoint}:${aws_rds_cluster.postgres.port}/${aws_rds_cluster.postgres.database_name}"
        },
        {
          name  = "REDIS_CONNECTION_STRING"
          value = "rediss://:${random_password.redis_password.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379"
        },
        {
          name  = "CLICKHOUSE_PASSWORD"
          value = random_password.clickhouse_password.result
        },
        {
          name  = "NEXTAUTH_SECRET"
          value = random_password.nextauth_secret.result
        },
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.langfuse_worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      essential = true
    }
  ])

  tags = {
    Name        = "${var.environment_name}-langfuse-worker"
    Environment = var.environment_name
  }
}

# ECS Service for Langfuse Web
resource "aws_ecs_service" "langfuse_web" {
  name            = "${var.environment_name}-langfuse-web"
  cluster         = aws_ecs_cluster.langfuse.id
  task_definition = aws_ecs_task_definition.langfuse_web.arn
  desired_count   = var.web_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.langfuse_web.arn
    container_name   = "langfuse-web"
    container_port   = 3000
  }
  depends_on = [aws_lb_target_group.langfuse_web]

  tags = {
    Name        = "${var.environment_name}-langfuse-web"
    Environment = var.environment_name
  }
}

# ECS Service for Langfuse Worker
resource "aws_ecs_service" "langfuse_worker" {
  name            = "${var.environment_name}-langfuse-worker"
  cluster         = aws_ecs_cluster.langfuse.id
  task_definition = aws_ecs_task_definition.langfuse_worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.langfuse_worker.arn
    container_name   = "langfuse-worker"
    container_port   = 3030
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-worker"
    Environment = var.environment_name
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "langfuse_web" {
  name              = "/ecs/${var.environment_name}-langfuse-web"
  retention_in_days = 30

  tags = {
    Name        = "${var.environment_name}-langfuse-web-logs"
    Environment = var.environment_name
  }
}

resource "aws_cloudwatch_log_group" "langfuse_worker" {
  name              = "/ecs/${var.environment_name}-langfuse-worker"
  retention_in_days = 30

  tags = {
    Name        = "${var.environment_name}-langfuse-worker-logs"
    Environment = var.environment_name
  }
}
