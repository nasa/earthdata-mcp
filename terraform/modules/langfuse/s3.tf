# S3 Bucket for Langfuse
resource "aws_s3_bucket" "langfuse" {
  bucket = "${var.environment_name}-langfuse-storage"

  tags = {
    Name        = "${var.environment_name}-langfuse-storage"
    Environment = var.environment_name
    Service     = "langfuse"
  }
}

resource "aws_s3_bucket_versioning" "langfuse" {
  bucket = aws_s3_bucket.langfuse.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle rules for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "langfuse" {
  bucket = aws_s3_bucket.langfuse.id

  rule {
    id     = "langfuse_lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER_IR"
    }

    # Optional: Delete old versions after 1 year
    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# IAM policy for S3 access
resource "aws_iam_policy" "langfuse_s3_access" {
  name        = "${var.environment_name}-langfuse-s3-access"
  description = "IAM policy for Langfuse S3 access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:DeleteObject",
          "s3:GetObjectVersion"
        ]
        Resource = [
          aws_s3_bucket.langfuse.arn,
          "${aws_s3_bucket.langfuse.arn}/*"
        ]
      }
    ]
  })

  tags = {
    Name        = "${var.environment_name}-langfuse-s3-policy"
    Environment = var.environment_name
  }
}

# Attach S3 policy to ECS task role
resource "aws_iam_role_policy_attachment" "langfuse_s3_access" {
  policy_arn = aws_iam_policy.langfuse_s3_access.arn
  role       = aws_iam_role.ecs_task_role.name
}
