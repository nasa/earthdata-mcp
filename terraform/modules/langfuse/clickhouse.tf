# Random password for ClickHouse
resource "random_password" "clickhouse_password" {
  length      = 64
  special     = false
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

# Security Group for ClickHouse
resource "aws_security_group" "clickhouse" {
  name        = "${var.environment_name}-langfuse-clickhouse"
  description = "Security group for ClickHouse"
  vpc_id      = var.vpc_id

  # HTTP interface
  ingress {
    from_port       = 8123
    to_port         = 8123
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  # Native TCP interface
  ingress {
    from_port       = 9000
    to_port         = 9000
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-clickhouse"
    Environment = var.environment_name
  }
}

# CloudWatch Log Group for ClickHouse
resource "aws_cloudwatch_log_group" "clickhouse" {
  name              = "/ecs/${var.environment_name}-langfuse-clickhouse"
  retention_in_days = 7

  tags = {
    Name        = "${var.environment_name}-langfuse-clickhouse-logs"
    Environment = var.environment_name
  }
}

# ClickHouse Task Definition
resource "aws_ecs_task_definition" "clickhouse" {
  family                   = "${var.environment_name}-langfuse-clickhouse"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 8192
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  volume {
    name = "clickhouse-data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.langfuse.id
      root_directory = "/"
      transit_encryption = "ENABLED"
      transit_encryption_port = 3049
    }
  }

  container_definitions = jsonencode([
    {
      name  = "clickhouse"
      image = var.clickhouse_image
      
      cpu       = 1024
      memory    = 8192
      essential = true

      mountPoints = [
        {
          sourceVolume  = "clickhouse-data"
          containerPath = "/var/lib/clickhouse"
          readOnly      = false
        }
      ]

      portMappings = [
        {
          // ClickHouse HTTP interface
          containerPort = 8123
          hostPort      = 8123
          protocol      = "tcp"
        },
        {
          // ClickHouse native interface
          containerPort = 9000
          hostPort      = 9000
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "CLICKHOUSE_DB"
          value = "langfuse"
        },
        {
          name  = "CLICKHOUSE_USER"
          value = "langfuse"
        },
        {
          name  = "CLICKHOUSE_PASSWORD"
          value = random_password.clickhouse_password.result
        },
        {
          name  = "CLICKHOUSE_CLUSTER_ENABLED"
          value = "false"
        },
        {
          name = "AWS_REGION"
          value = var.aws_region
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:8123/ping || exit 1"]
        interval    = 5
        timeout     = 5
        retries     = 10
        startPeriod = 1
      }
      
      
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.clickhouse.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      essential = true
    }
  ])

  tags = {
    Name        = "${var.environment_name}-langfuse-clickhouse"
    Environment = var.environment_name
  }
}

# ECS Service for ClickHouse
resource "aws_ecs_service" "clickhouse" {
  name            = "${var.environment_name}-langfuse-clickhouse"
  cluster         = aws_ecs_cluster.langfuse.id
  task_definition = aws_ecs_task_definition.clickhouse.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.clickhouse.id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.clickhouse.arn
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-clickhouse"
    Environment = var.environment_name
  }

  depends_on = [aws_efs_mount_target.langfuse]
}
