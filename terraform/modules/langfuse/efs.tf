# EFS File System
resource "aws_efs_file_system" "langfuse" {
  creation_token  = "${var.environment_name}-langfuse-efs"
  encrypted       = true
  throughput_mode = "elastic"

  tags = {
    Name        = "${var.environment_name}-langfuse-efs"
    Environment = var.environment_name
  }
}

# Mount targets in each subnet
resource "aws_efs_mount_target" "langfuse" {
  count           = length(var.subnet_ids)
  file_system_id  = aws_efs_file_system.langfuse.id
  subnet_id       = var.subnet_ids[count.index]
  security_groups = [aws_security_group.efs.id]
}


# Security group for EFS
resource "aws_security_group" "efs" {
  name        = "${var.environment_name}-langfuse-efs"
  description = "Security group for EFS"
  vpc_id      = var.vpc_id

  ingress {
    description = "NFS from VPC"
    from_port   = 2049
    to_port     = 2049
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
    Name        = "${var.environment_name}-langfuse-efs"
    Environment = var.environment_name
  }
}

# EFS Access Point for ClickHouse
resource "aws_efs_access_point" "clickhouse" {
  file_system_id = aws_efs_file_system.langfuse.id

  root_directory {
    path = "/clickhouse"
    creation_info {
      owner_gid   = 1001
      owner_uid   = 1001
      permissions = "0755"
    }
  }

  posix_user {
    gid = 1001
    uid = 1001
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-clickhouse"
    Environment = var.environment_name
  }
}


resource "aws_efs_access_point" "langfuse_storage" {
  file_system_id = aws_efs_file_system.langfuse.id

  root_directory {
    path = "/langfuse"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "0755"
    }
  }

  posix_user {
    gid = 1000
    uid = 1000
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-storage"
    Environment = var.environment_name
  }
}
