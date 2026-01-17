# Target Group for Langfuse Web
resource "aws_lb_target_group" "langfuse_web" {
  name        = "${var.environment_name}-langfuse-web"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

health_check {
  enabled             = true
  healthy_threshold   = 2
  interval            = 30
  matcher             = "200"
  path                = var.base_path
  timeout             = 5
  unhealthy_threshold = 3
}

  tags = {
    Name        = "${var.environment_name}-langfuse-web-tg"
    Environment = var.environment_name
  }
}

resource "aws_lb_listener_rule" "langfuse" {
  listener_arn = var.lb_listener
  priority     = 82

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.langfuse_web.arn
  }

  condition {
    path_pattern {
      values = [var.base_path, "${var.base_path}/*"]
    }
  }
}

data "aws_lb" "lb_name" {
  name = "cmr-services-${var.environment_name}"
}
resource "aws_lb_target_group" "langfuse_worker" {
   name        = "${var.environment_name}-langfuse-worker"
  port        = 3030
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
}

resource "aws_lb_listener" "langfuse-worker" {
  load_balancer_arn = data.aws_lb.lb_name.arn
  port              = 3030  # Different port for worker
  protocol          = "HTTP"

  default_action {
    type             = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Not found"
      status_code = "404"
    }
    target_group_arn = aws_lb_target_group.langfuse_worker.arn
  }

  tags = {
    Name        = "${var.environment_name}-langfuse-worker-listener"
    Environment = var.environment_name
  }
}
resource "aws_lb_listener_rule" "langfuse-worker" {
  listener_arn = aws_lb_listener.langfuse-worker.arn

  priority = 1

  action {
    type = "forward"
    target_group_arn = aws_lb_target_group.langfuse_worker.arn
  }

  condition {
    path_pattern {
      values = ["/api*"]
    }

  }

  condition {
    source_ip {
      values = [var.vpc_cidr_block]
    }
  }
}
