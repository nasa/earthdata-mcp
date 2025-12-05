# Service Discovery Namespace
resource "aws_service_discovery_private_dns_namespace" "langfuse" {
  name = "${var.environment_name}-langfuse.local"
  vpc  = var.vpc_id

  tags = {
    Name        = "${var.environment_name}-langfuse-service-discovery"
    Environment = var.environment_name
  }
}

# Service Discovery Service for ClickHouse
resource "aws_service_discovery_service" "clickhouse" {
  name = "${var.environment_name}-langfuse-clickhouse"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.langfuse.id
    
    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-clickhouse"
    Environment = var.environment_name
  }
}
