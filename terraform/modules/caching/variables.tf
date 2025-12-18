variable "environment_name" {
  description = "environment name, e.g. sit, uat, prod"
  type = string
}

variable "subnet_ids" {
    description = "Subnet ID"
    type        = list(string)
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

variable "vpc_id" {
    description = "VPC ID"
    type = string
}

variable "vpc_cidr_block" {
  description = "VPC CIDR block"
  type = string
}
