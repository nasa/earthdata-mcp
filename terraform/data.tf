# Get VPC by tag filter
data "aws_vpc" "app" {
  filter {
    name   = "tag:Name"
    values = [var.vpc_tag_name_filter]
  }
}

# Get subnets by VPC and tag filter
data "aws_subnets" "app" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.app.id]
  }

  tags = {
    Name = var.subnet_tag_name_filter
  }
}

data "aws_lb" "cmr_lb" {
  name = "cmr-services-${var.environment_name}"
}

data "aws_lb_listener" "cmr_lb_listener" {
  load_balancer_arn = data.aws_lb.cmr_lb.arn
  port              = 443
}