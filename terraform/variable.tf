variable "environment_name" {
  description = "Environment name, e.g. dev, test, prod"
  type        = string
}

variable "aws_region" {
  description = "AWS region to deploy to"
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
