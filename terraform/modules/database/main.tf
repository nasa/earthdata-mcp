# Random password for master user
resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# DB subnet group
resource "aws_db_subnet_group" "main" {
  name_prefix = "${var.environment_name}-earthdata-mcp-db-"
  description = "Subnet group for earthdata-mcp database"
  subnet_ids  = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-db"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Security group for RDS
resource "aws_security_group" "database" {
  name_prefix = "${var.environment_name}-earthdata-mcp-db-sg-"
  description = "Security group for earthdata-mcp PostgreSQL database"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-db-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Allow inbound from specified security groups
resource "aws_security_group_rule" "inbound_from_sg" {
  count = length(var.allowed_security_group_ids)

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = var.allowed_security_group_ids[count.index]
  security_group_id        = aws_security_group.database.id
  description              = "PostgreSQL from allowed security group"
}

# Allow inbound from specified CIDR blocks
resource "aws_security_group_rule" "inbound_from_cidr" {
  count = length(var.allowed_cidr_blocks) > 0 ? 1 : 0

  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  cidr_blocks       = var.allowed_cidr_blocks
  security_group_id = aws_security_group.database.id
  description       = "PostgreSQL from allowed CIDR blocks"
}

# Parameter group for pgvector
resource "aws_db_parameter_group" "pgvector" {
  name_prefix = "${var.environment_name}-earthdata-mcp-db-params-"
  family      = "postgres${split(".", var.engine_version)[0]}"
  description = "Parameter group for earthdata-mcp database with pgvector support"

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-db-params"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# RDS PostgreSQL instance
resource "aws_db_instance" "main" {
  identifier = "${var.environment_name}-earthdata-mcp-db"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = var.master_username
  password = random_password.master.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  parameter_group_name   = aws_db_parameter_group.pgvector.name

  publicly_accessible = false
  multi_az            = var.environment_name == "prod" ? true : false

  backup_retention_period = var.backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.environment_name}-earthdata-mcp-db-final"

  # Enable Performance Insights for debugging
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  tags = merge(var.tags, {
    Name = "${var.environment_name}-earthdata-mcp-db"
  })
}
