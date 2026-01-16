# Ingest Queue - receives from SNS, triggers ingest lambda
resource "aws_sqs_queue" "ingest_dlq" {
  name                      = "${var.environment_name}-earthdata-mcp-ingest-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-ingest-dlq"
  })
}

resource "aws_sqs_queue" "ingest" {
  name = "${var.environment_name}-earthdata-mcp-ingest"

  visibility_timeout_seconds = var.ingest_lambda_timeout * 6
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20     # Long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingest_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-ingest"
  })
}

# Policy to allow SNS to send to ingest queue
resource "aws_sqs_queue_policy" "ingest" {
  queue_url = aws_sqs_queue.ingest.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowSNSPublish"
        Effect    = "Allow"
        Principal = { Service = "sns.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.ingest.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = var.cmr_sns_topic_arn
          }
        }
      }
    ]
  })
}

# SNS subscription
resource "aws_sns_topic_subscription" "cmr_ingest" {
  topic_arn = var.cmr_sns_topic_arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.ingest.arn

  raw_message_delivery = false
}

# Embedding FIFO Queue - receives from ingest lambda, triggers embedding lambda
resource "aws_sqs_queue" "embedding_dlq" {
  name                      = "${var.environment_name}-earthdata-mcp-embedding-dlq.fifo"
  fifo_queue                = true
  message_retention_seconds = 1209600 # 14 days

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-embedding-dlq"
  })
}

resource "aws_sqs_queue" "embedding" {
  name       = "${var.environment_name}-earthdata-mcp-embedding.fifo"
  fifo_queue = true

  content_based_deduplication = false
  deduplication_scope         = "messageGroup"
  fifo_throughput_limit       = "perMessageGroupId"

  visibility_timeout_seconds = var.embedding_lambda_timeout * 6
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.embedding_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-embedding"
  })
}
