terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

resource "aws_lb_target_group" "ecs_tg" {
  name        = "${var.ecs_service_name}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/"
    interval            = 300
    timeout             = 120
    healthy_threshold   = 2
    unhealthy_threshold = 2
    matcher             = "200-299,301-399"
    port = var.container_port
  }
}

