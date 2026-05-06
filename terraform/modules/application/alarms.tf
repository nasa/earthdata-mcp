# CloudWatch Alarms for monitoring queue health and Lambda failures
#
# These alarms help detect processing failures and performance issues.

# =============================================================================
# Dead Letter Queue Alarms
# =============================================================================

# Alarm: Ingest DLQ has messages
# Triggers when CMR events fail to process after 3 retries


# Alarm: Embedding DLQ has messages
# Triggers when embedding generation fails after 3 retries


# =============================================================================
# Queue Backlog Alarms
# =============================================================================

# Alarm: Ingest queue backlog growing


# Alarm: Embedding queue backlog growing


# =============================================================================
# Step Function Alarms
# =============================================================================

# Alarm: Enrichment Step Function execution failures


# Alarm: Enrichment Step Function execution throttles


# =============================================================================
# Lambda Error Alarms
# =============================================================================

# Alarm: Ingest Lambda errors


# Alarm: Embedding Lambda errors


# Alarm: Bootstrap Lambda errors


# Alarm: Enrichment Lambda errors


# =============================================================================
# Lambda Throttling Alarms
# =============================================================================

# Alarm: Ingest Lambda throttled


# Alarm: Enrichment Lambda throttled
# Expected during bootstrap when Step Function fan-out exceeds the
# concurrency limit. SFN retries handle this gracefully, but sustained
# throttling indicates enrichment_lambda_concurrency is too low.


# Alarm: Embedding Lambda throttled


# =============================================================================
# Lambda Duration Alarms (approaching timeout)
# =============================================================================

# Alarm: Ingest Lambda duration approaching timeout


# Alarm: Embedding Lambda duration approaching timeout


# Alarm: Enrichment Lambda duration approaching timeout


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
