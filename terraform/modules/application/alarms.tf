# CloudWatch Alarms for monitoring queue health and Lambda failures
#
# These alarms help detect processing failures and performance issues.

# =============================================================================
# Dead Letter Queue Alarms
# =============================================================================

# Alarm: Ingest DLQ has messages
# Triggers when CMR events fail to process after 3 retries
resource "aws_cloudwatch_metric_alarm" "ingest_dlq" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-ingest-dlq"
  alarm_description   = "Messages in ingest DLQ - CMR events failed to process"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.ingest_dlq.name
  }

  tags = var.tags
}

# Alarm: Embedding DLQ has messages
# Triggers when embedding generation fails after 3 retries
resource "aws_cloudwatch_metric_alarm" "embedding_dlq" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-embedding-dlq"
  alarm_description   = "Messages in embedding DLQ - embedding generation failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.embedding_dlq.name
  }

  tags = var.tags
}

# =============================================================================
# Queue Backlog Alarms
# =============================================================================

# Alarm: Ingest queue backlog growing
resource "aws_cloudwatch_metric_alarm" "ingest_backlog" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-ingest-backlog"
  alarm_description   = "Ingest queue backlog exceeds threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 1000
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.ingest.name
  }

  tags = var.tags
}

# Alarm: Embedding queue backlog growing
resource "aws_cloudwatch_metric_alarm" "embedding_backlog" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-embedding-backlog"
  alarm_description   = "Embedding queue backlog exceeds threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 5000
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.embedding.name
  }

  tags = var.tags
}

# =============================================================================
# Lambda Error Alarms
# =============================================================================

# Alarm: Ingest Lambda errors
resource "aws_cloudwatch_metric_alarm" "ingest_lambda_errors" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-ingest-errors"
  alarm_description   = "Ingest Lambda invocation errors detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.ingest.function_name
  }

  tags = var.tags
}

# Alarm: Embedding Lambda errors
resource "aws_cloudwatch_metric_alarm" "embedding_lambda_errors" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-embedding-errors"
  alarm_description   = "Embedding Lambda invocation errors detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.embedding.function_name
  }

  tags = var.tags
}

# Alarm: Bootstrap Lambda errors
resource "aws_cloudwatch_metric_alarm" "bootstrap_lambda_errors" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-bootstrap-errors"
  alarm_description   = "Bootstrap Lambda invocation errors detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.bootstrap.function_name
  }

  tags = var.tags
}

# =============================================================================
# Lambda Throttling Alarms
# =============================================================================

# Alarm: Ingest Lambda throttled
resource "aws_cloudwatch_metric_alarm" "ingest_lambda_throttles" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-ingest-throttles"
  alarm_description   = "Ingest Lambda is being throttled"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.ingest.function_name
  }

  tags = var.tags
}

# Alarm: Embedding Lambda throttled
resource "aws_cloudwatch_metric_alarm" "embedding_lambda_throttles" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-embedding-throttles"
  alarm_description   = "Embedding Lambda is being throttled"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.embedding.function_name
  }

  tags = var.tags
}

# =============================================================================
# Lambda Duration Alarms (approaching timeout)
# =============================================================================

# Alarm: Ingest Lambda duration approaching timeout
resource "aws_cloudwatch_metric_alarm" "ingest_lambda_duration" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-ingest-duration"
  alarm_description   = "Ingest Lambda duration approaching timeout (>80%)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  # Alert when average duration exceeds 80% of timeout
  threshold           = var.ingest_lambda_timeout * 1000 * 0.8
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.ingest.function_name
  }

  tags = var.tags
}

# Alarm: Embedding Lambda duration approaching timeout
resource "aws_cloudwatch_metric_alarm" "embedding_lambda_duration" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-embedding-duration"
  alarm_description   = "Embedding Lambda duration approaching timeout (>80%)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  # Alert when average duration exceeds 80% of timeout
  threshold           = var.embedding_lambda_timeout * 1000 * 0.8
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.embedding.function_name
  }

  tags = var.tags
}

# =============================================================================
# MCP Server Alarms (ECS Fargate)
# =============================================================================

# Alarm: MCP server unhealthy targets
resource "aws_cloudwatch_metric_alarm" "mcp_unhealthy_targets" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-server-unhealthy"
  alarm_description   = "MCP server has unhealthy targets in target group"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    TargetGroup  = aws_lb_target_group.mcp.arn_suffix
    LoadBalancer = data.aws_lb.public.arn_suffix
  }

  tags = var.tags
}

# Alarm: MCP server no healthy targets
resource "aws_cloudwatch_metric_alarm" "mcp_no_healthy_targets" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-server-no-targets"
  alarm_description   = "MCP server has no healthy targets"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 1
  treat_missing_data  = "breaching"

  dimensions = {
    TargetGroup  = aws_lb_target_group.mcp.arn_suffix
    LoadBalancer = data.aws_lb.public.arn_suffix
  }

  tags = var.tags
}

# Alarm: MCP server high CPU utilization
resource "aws_cloudwatch_metric_alarm" "mcp_cpu_high" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-server-cpu-high"
  alarm_description   = "MCP server CPU utilization exceeds 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.mcp.name
    ServiceName = aws_ecs_service.mcp.name
  }

  tags = var.tags
}

# Alarm: MCP server high memory utilization
resource "aws_cloudwatch_metric_alarm" "mcp_memory_high" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-server-memory-high"
  alarm_description   = "MCP server memory utilization exceeds 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.mcp.name
    ServiceName = aws_ecs_service.mcp.name
  }

  tags = var.tags
}

# Alarm: MCP server 5xx errors (from container)
resource "aws_cloudwatch_metric_alarm" "mcp_5xx_errors" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-server-5xx"
  alarm_description   = "MCP server returning 5xx errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    TargetGroup  = aws_lb_target_group.mcp.arn_suffix
    LoadBalancer = data.aws_lb.public.arn_suffix
  }

  tags = var.tags
}

# Alarm: MCP server 4xx errors (from container)
resource "aws_cloudwatch_metric_alarm" "mcp_4xx_errors" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-server-4xx"
  alarm_description   = "MCP server returning elevated 4xx errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_4XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 50
  treat_missing_data  = "notBreaching"

  dimensions = {
    TargetGroup  = aws_lb_target_group.mcp.arn_suffix
    LoadBalancer = data.aws_lb.public.arn_suffix
  }

  tags = var.tags
}
