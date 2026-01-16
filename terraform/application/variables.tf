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

# Bedrock
variable "embedding_model" {
  description = "Bedrock embedding model ID"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "bedrock_region" {
  description = "AWS region for Bedrock"
  type        = string
  default     = "us-east-1"
}

# Database table names
variable "embeddings_table" {
  description = "Name of the embeddings table in PostgreSQL"
  type        = string
  default     = "concept_embeddings"
}

variable "associations_table" {
  description = "Name of the concept associations table in PostgreSQL"
  type        = string
  default     = "concept_associations"
}

variable "kms_embeddings_table" {
  description = "Name of the KMS embeddings table in PostgreSQL"
  type        = string
  default     = "kms_embeddings"
}

variable "kms_associations_table" {
  description = "Name of the concept-KMS associations table in PostgreSQL"
  type        = string
  default     = "concept_kms_associations"
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
  default     = 10
}

variable "embedding_lambda_timeout" {
  description = "Timeout for embedding lambda in seconds"
  type        = number
  default     = 300
}

variable "embedding_lambda_memory" {
  description = "Memory for embedding lambda in MB"
  type        = number
  default     = 512
}

variable "embedding_lambda_concurrency" {
  description = "Reserved concurrent executions for embedding lambda"
  type        = number
  default     = 50
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

variable "langfuse_secret_key" {
  description = "Langfuse secret key"
  type        = string
  default     = ""
  sensitive   = true
}
