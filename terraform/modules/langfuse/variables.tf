variable "environment_name" {
  description = "environment name, e.g. sit, uat, prod"
}

variable "vpc_id" {
    description = "VPC ID"
    type = string
}

variable "vpc_cidr_block" {
  description = "VPC CIDR block"
  type = string
}

variable "subnet_ids" {
    description = "Subnet ID"
    type        = list(string)
}

# Redis configuration variables
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

variable "redis_at_rest_encryption" {
  description = "Enable at-rest encryption for Redis"
  type        = bool
  default     = true
}

variable "vpc_tag_name_filter" {
  type    = string
  default = null
}

variable "subnet_tag_name_filter" {
  type    = string
  default = null
}

# ECS Configuration
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "web_cpu" {
  description = "CPU units for web service"
  type        = number
  default     = 512
}

variable "web_memory" {
  description = "Memory for web service"
  type        = number
  default     = 1024
}

variable "worker_cpu" {
  description = "CPU units for worker service"
  type        = number
  default     = 2048
}

variable "worker_memory" {
  description = "Memory for worker service"
  type        = number
  default     = 4096
}

variable "web_desired_count" {
  description = "Desired number of web tasks"
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Desired number of worker tasks"
  type        = number
  default     = 1
}

# ClickHouse cluster configuration
variable "clickhouse_instance_count" {
  description = "Number of ClickHouse instances"
  type        = number
  default     = 1
}

variable "clickhouse_image" {
  description = "ClickHouse Docker image"
  type        = string
  default     = "clickhouse/clickhouse-server:latest"
}

variable "clickhouse_cpu" {
  description = "CPU units for ClickHouse"
  type        = number
  default     = 512
}

variable "clickhouse_memory" {
  description = "Memory for ClickHouse"
  type        = number
  default     = 1024
}

variable "lb_listener" {
  type = string
}

variable "load_balancer_dns" {
  description = "Load balancer DNS name"
  type        = string
}

# ECR Image URLs
variable "langfuse_web_image" {
  description = "Langfuse web Docker image URL"
  type        = string
}

variable "langfuse_worker_image" {
  description = "Langfuse worker Docker image URL"
  type        = string
}
