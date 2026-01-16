variable "environment_name" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_tag_name_filter" {
  description = "VPC tag name to filter on"
  type        = string
}

variable "subnet_tag_name_filter" {
  description = "Subnet tag name to filter on"
  type        = string
}

variable "load_balancer_name" {
  description = "Name of the existing load balancer to attach Langfuse to"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag for Langfuse containers"
  type        = string
  default     = "latest"
}

variable "base_path" {
  description = "Base path for Langfuse web UI and API"
  type        = string
  default     = "/langfuse"
}

# Langfuse ECS configuration
variable "web_cpu" {
  description = "CPU units for Langfuse web service"
  type        = number
  default     = 2048
}

variable "web_memory" {
  description = "Memory for Langfuse web service in MB"
  type        = number
  default     = 4096
}

variable "worker_cpu" {
  description = "CPU units for Langfuse worker service"
  type        = number
  default     = 2048
}

variable "worker_memory" {
  description = "Memory for Langfuse worker service in MB"
  type        = number
  default     = 4096
}

variable "web_desired_count" {
  description = "Desired number of Langfuse web tasks"
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Desired number of Langfuse worker tasks"
  type        = number
  default     = 1
}

# Langfuse Redis configuration
variable "redis_node_type" {
  description = "ElastiCache node type for Langfuse Redis"
  type        = string
  default     = "cache.t3.small"
}

# Langfuse ClickHouse configuration
variable "clickhouse_cpu" {
  description = "CPU units for Langfuse ClickHouse"
  type        = number
  default     = 2048
}

variable "clickhouse_memory" {
  description = "Memory for Langfuse ClickHouse in MB"
  type        = number
  default     = 4096
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
