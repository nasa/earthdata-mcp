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
