# CloudWatch Alarms for RDS PostgreSQL monitoring
#
# These alarms help detect database performance and capacity issues.

# =============================================================================
# CPU Alarms
# =============================================================================

# Alarm: High CPU utilization
resource "aws_cloudwatch_metric_alarm" "db_cpu_high" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-db-cpu-high"
  alarm_description   = "Database CPU utilization exceeds 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = var.tags
}

# =============================================================================
# Memory Alarms
# =============================================================================

# Alarm: Low freeable memory
# FreeableMemory is in bytes, alert when below 256MB
resource "aws_cloudwatch_metric_alarm" "db_memory_low" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-db-memory-low"
  alarm_description   = "Database freeable memory below 256MB"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "FreeableMemory"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 268435456 # 256MB in bytes
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = var.tags
}

# =============================================================================
# Storage Alarms
# =============================================================================

# Alarm: Low free storage space
# FreeStorageSpace is in bytes, alert when below 5GB
resource "aws_cloudwatch_metric_alarm" "db_storage_low" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-db-storage-low"
  alarm_description   = "Database free storage below 5GB"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120 # 5GB in bytes
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = var.tags
}

# =============================================================================
# Connection Alarms
# =============================================================================

# Alarm: High database connections
# db.t3.medium has max_connections ~112, alert at 90
resource "aws_cloudwatch_metric_alarm" "db_connections_high" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-db-connections-high"
  alarm_description   = "Database connections exceeding threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 90
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = var.tags
}

# =============================================================================
# I/O Alarms
# =============================================================================

# Alarm: High read latency
# Alert when average read latency exceeds 20ms
resource "aws_cloudwatch_metric_alarm" "db_read_latency_high" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-db-read-latency"
  alarm_description   = "Database read latency exceeds 20ms"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ReadLatency"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 0.02 # 20ms in seconds
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = var.tags
}

# Alarm: High write latency
# Alert when average write latency exceeds 20ms
resource "aws_cloudwatch_metric_alarm" "db_write_latency_high" {
  alarm_name          = "${var.environment_name}-earthdata-mcp-db-write-latency"
  alarm_description   = "Database write latency exceeds 20ms"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "WriteLatency"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 0.02 # 20ms in seconds
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = var.tags
}
