# Security group for PostgreSQL
resource "aws_security_group" "postgres" {
  name        = "${var.environment_name}-langfuse-postgres"
  description = "Security group for Langfuse PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-postgres"
    Environment = var.environment_name
  }
}

# Random password for PostgreSQL
resource "random_password" "postgres_password" {
  length      = 64
  special     = false
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

# DB subnet group
resource "aws_db_subnet_group" "postgres" {
  name        = "cmr-${var.environment_name}-langfuse-postgres-subnet-group"
  description = "Subnet group for Langfuse PostgreSQL"
  subnet_ids  = var.subnet_ids

  tags = {
    Name        = "${var.environment_name}-langfuse-postgres-subnet-group"
    Environment = var.environment_name
  }
}

# Aurora PostgreSQL Serverless v2 Cluster
resource "aws_rds_cluster" "postgres" {
  cluster_identifier           = "${var.environment_name}-langfuse-postgres"
  engine                       = "aurora-postgresql"
  engine_version               = "17"
  database_name                = "langfuse"
  master_username              = "langfuse"
  master_password              = random_password.postgres_password.result
  db_subnet_group_name         = aws_db_subnet_group.postgres.name
  vpc_security_group_ids       = [aws_security_group.postgres.id]

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 1
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-postgres"
    Environment = var.environment_name
  }
}

resource "aws_rds_cluster_instance" "postgres" {
  count              = 1  # Start with 1 instance
  identifier         = "${var.environment_name}-langfuse-postgres-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.postgres.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.postgres.engine
  engine_version     = aws_rds_cluster.postgres.engine_version

  # Enable Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  tags = {
    Name        = "${var.environment_name}-langfuse-postgres-${count.index + 1}"
    Environment = var.environment_name
  }
}
