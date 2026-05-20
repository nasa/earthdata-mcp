# Data source for existing public load balancer
data "aws_lb" "public" {
  name = var.load_balancer_name
}

data "aws_lb_listener" "https" {
  load_balancer_arn = data.aws_lb.public.arn
  port              = 443
}

# ECS Cluster for MCP server
resource "aws_ecs_cluster" "mcp" {
  name = "${var.environment_name}-earthdata-mcp-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-cluster"
  })
}

# CloudWatch Log Group for MCP server
resource "aws_cloudwatch_log_group" "mcp_server" {
  name              = "/ecs/${var.environment_name}-earthdata-mcp-server"
  retention_in_days = 14

  tags = var.tags
}

# IAM role for ECS task execution
resource "aws_iam_role" "mcp_execution" {
  name = "${var.environment_name}-earthdata-mcp-execution-role"

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

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "mcp_execution" {
  role       = aws_iam_role.mcp_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM role for MCP task
resource "aws_iam_role" "mcp_task" {
  name = "${var.environment_name}-earthdata-mcp-task-role"

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

  tags = var.tags
}

resource "aws_iam_role_policy" "mcp_task" {
  name = "${var.environment_name}-earthdata-mcp-task-policy"
  role = aws_iam_role.mcp_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Bedrock"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-*",
          "arn:aws:bedrock:*:*:inference-profile/us.amazon.titan-embed-*",
          "arn:aws:bedrock:*::foundation-model/amazon.nova-pro-*",
          "arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-pro-*"
        ]
      },
      {
        Sid    = "SSMGetParameter"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/${var.environment_name}-langfuse-secret-key"
      },
      {
        Sid    = "KMSDecryptSSM"
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = "arn:aws:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:alias/aws/ssm"
      }
    ]
  })
}

# Security group for MCP server
resource "aws_security_group" "mcp_server" {
  name_prefix = "${var.environment_name}-earthdata-mcp-server-sg-"
  description = "Security group for MCP server"
  vpc_id      = var.vpc_id

  ingress {
    description     = "HTTP from ALB"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = tolist(data.aws_lb.public.security_groups)
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-server-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# ALB Target Group for MCP
resource "aws_lb_target_group" "mcp" {
  name_prefix = "mcp-"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/mcp/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-tg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# ALB Listener Rule for /mcp path
resource "aws_lb_listener_rule" "mcp" {
  listener_arn = data.aws_lb_listener.https.arn
  priority     = var.mcp_listener_priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp.arn
  }

  condition {
    path_pattern {
      values = ["/mcp", "/mcp/*"]
    }
  }

  tags = var.tags
}

# ECS Task Definition
resource "aws_ecs_task_definition" "mcp" {
  family                   = "${var.environment_name}-earthdata-mcp-server"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.mcp_server_cpu
  memory                   = var.mcp_server_memory
  execution_role_arn       = aws_iam_role.mcp_execution.arn
  task_role_arn            = aws_iam_role.mcp_task.arn

  container_definitions = jsonencode([
    {
      name  = "mcp-server"
      image = var.mcp_server_image

      portMappings = [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT_NAME"
          value = var.environment_name
        },
        {
          name  = "DB_HOST"
        },
        {
          name  = "CMR_URL"
          value = var.cmr_url
        },
        {
          name  = "ASSOCIATIONS_TABLE"
          value = var.associations_table
        },
        {
          name  = "LANGFUSE_BASE_URL"
          value = var.langfuse_host
        },
        {
          name  = "LANGFUSE_PUBLIC_KEY"
          value = var.langfuse_public_key
        },
        {
          name  = "GEOCODE_INDEX_HOST"
          value = var.geocode_index_host
        },
        {
          name  = "GEOCODE_INDEX_REGION"
          value = var.geocode_index_region
        },
        {
          name  = "GEOCODE_INDEX_PORT"
          value = var.geocode_index_port
        },
        {
          name  = "SIMPLIFY_GEOM_MAX_POINT"
          value = var.simplify_geom_max_point
        },
        {
          name  = "GRANULE_VALIDATION_MAX_WORKERS"
          value = var.granule_validation_max_workers
        },
        {
          name  = "TOOL_ASSOC_MAX_WORKERS"
          value = var.tool_assoc_max_workers
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.mcp_server.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "mcp"
        }
      }

      essential = true
    }
  ])

  tags = var.tags
}

# ECS Service
resource "aws_ecs_service" "mcp" {
  name            = "${var.environment_name}-earthdata-mcp-server"
  cluster         = aws_ecs_cluster.mcp.id
  task_definition = aws_ecs_task_definition.mcp.arn
  desired_count   = var.mcp_server_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.mcp_server.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.mcp.arn
    container_name   = "mcp-server"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener_rule.mcp]

  tags = var.tags

  lifecycle {
    ignore_changes = [desired_count]
  }
}

# ECS Autoscaling
resource "aws_appautoscaling_target" "mcp" {
  max_capacity       = var.mcp_server_max_count
  min_capacity       = var.mcp_server_min_count
  resource_id        = "service/${aws_ecs_cluster.mcp.name}/${aws_ecs_service.mcp.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "mcp_cpu" {
  name               = "${var.environment_name}-earthdata-mcp-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.mcp.resource_id
  scalable_dimension = aws_appautoscaling_target.mcp.scalable_dimension
  service_namespace  = aws_appautoscaling_target.mcp.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_policy" "mcp_memory" {
  name               = "${var.environment_name}-earthdata-mcp-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.mcp.resource_id
  scalable_dimension = aws_appautoscaling_target.mcp.scalable_dimension
  service_namespace  = aws_appautoscaling_target.mcp.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
