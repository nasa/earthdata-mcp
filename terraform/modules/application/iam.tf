# Get current AWS account ID
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# IAM role for ingest lambda




# IAM role for embedding lambda




# Security group for embedding lambda (VPC access to RDS)


# HTTPS egress for CMR, Bedrock, Secrets Manager


# Allow embedding lambda to connect to database (direct)


# Allow embedding lambda to connect to RDS Proxy
