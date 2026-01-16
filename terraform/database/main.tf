# Data sources for VPC and subnets
data "aws_vpc" "main" {
  filter {
    name   = "tag:Name"
    values = [var.vpc_tag_name_filter]
  }
}

data "aws_subnets" "main" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }

  tags = {
    Name = var.subnet_tag_name_filter
  }
}

# Database module
module "database" {
  source = "../modules/database"

  environment_name = var.environment_name
  vpc_id           = data.aws_vpc.main.id
  subnet_ids       = data.aws_subnets.main.ids

  instance_class        = var.instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  engine_version        = var.engine_version
  database_name         = var.database_name
  master_username       = var.master_username

  backup_retention_period = var.backup_retention_period
  deletion_protection     = var.deletion_protection
  skip_final_snapshot     = var.skip_final_snapshot

  tags = var.tags
}
