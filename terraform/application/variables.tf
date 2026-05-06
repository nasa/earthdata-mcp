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

# SNS
variable "cmr_sns_topic_name" {
  description = "Name of the CMR SNS topic to subscribe to"
  type        = string
}

# Image tag for lambda containers
variable "image_tag" {
  description = "Docker image tag for lambda containers"
  type        = string
  default     = "latest"
}

# CMR
variable "cmr_url" {
  description = "CMR API base URL"
  type        = string
  default     = "https://cmr.earthdata.nasa.gov"
}

# Database table names


variable "associations_table" {
  description = "Name of the associations table in PostgreSQL"
  type        = string
  default     = "associations"
}

# Lambda configuration
variable "ingest_lambda_timeout" {
  description = "Timeout for ingest lambda in seconds"
  type        = number
  default     = 30
}

variable "ingest_lambda_memory" {
  description = "Memory for ingest lambda in MB"
  type        = number
  default     = 256
}

variable "ingest_lambda_concurrency" {
  description = "Reserved concurrent executions for ingest lambda"
  type        = number
  default     = 5
}







variable "enrichment_lambda_concurrency" {
  description = "Reserved concurrent executions for enrichment lambda. Controls Step Function pipeline throughput — each collection requires 7+ sequential Lambda invocations."
  type        = number
  default     = 200
}

variable "bootstrap_lambda_concurrency" {
  description = "Reserved concurrent executions for bootstrap lambda. Caps bulk-load flood into the embedding queue."
  type        = number
  default     = 40
}

variable "bootstrap_lambda_timeout" {
  description = "Timeout for bootstrap lambda in seconds"
  type        = number
  default     = 900
}

variable "bootstrap_lambda_memory" {
  description = "Memory for bootstrap lambda in MB"
  type        = number
  default     = 512
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "langfuse_host" {
  description = "Langfuse host URL"
  type        = string
  default     = ""
}

variable "langfuse_public_key" {
  description = "Langfuse public key"
  type        = string
  default     = ""
}

# MCP Server
variable "load_balancer_name" {
  description = "Name of the existing public ALB"
  type        = string
}

variable "mcp_server_cpu" {
  description = "CPU units for MCP server task (1024 = 1 vCPU)"
  type        = number
  default     = 256
}

variable "mcp_server_memory" {
  description = "Memory for MCP server task in MB"
  type        = number
  default     = 512
}

variable "mcp_server_desired_count" {
  description = "Desired number of MCP server tasks"
  type        = number
  default     = 1
}

variable "mcp_server_min_count" {
  description = "Minimum number of MCP server tasks for autoscaling"
  type        = number
  default     = 1
}

variable "mcp_server_max_count" {
  description = "Maximum number of MCP server tasks for autoscaling"
  type        = number
  default     = 4
}

variable "mcp_listener_priority" {
  description = "Priority for MCP ALB listener rule"
  type        = number
  default     = 200
}

# Geocode Index (OpenSearch)
variable "geocode_index_host" {
  description = "OpenSearch host for the geocode index used by the natural language geocoder"
  type        = string
  default     = ""
}

variable "geocode_index_region" {
  description = "AWS region of the geocode index OpenSearch domain"
  type        = string
  default     = ""
}

variable "geocode_index_port" {
  description = "Port for the geocode index OpenSearch domain"
  type        = string
  default     = ""
}

variable "simplify_geom_max_point" {
  description = "Maximum number of points for simplified geometries"
  type        = string
  default     = "4900"
}

variable "granule_validation_max_workers" {
  description = "Max concurrent threads for granule availability checks in the MCP server"
  type        = string
  default     = "10"
}

variable "tool_assoc_max_workers" {
  description = "Max concurrent threads for fetching CMR tool associations and collection tags in the MCP server"
  type        = string
  default     = "10"
}
