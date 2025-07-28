terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}
resource "aws_lb" "alb" {
    name               = var.alb_name
    internal           = false
    load_balancer_type = "application"
    security_groups    = var.alb_security_groups
    subnets            = var.alb_subnets

    tags = {
        Name = var.alb_name
    }
}

resource "aws_alb_listener" "https_alb_listener" {
  load_balancer_arn = aws_lb.alb.arn
  port = 443
  protocol = "HTTPS"
  certificate_arn = var.certificate_arn

  default_action {
    type = "forward"
    target_group_arn = var.target_group_arn
  }
}

resource "aws_alb_listener" "http_alb_listener" {
  load_balancer_arn = aws_lb.alb.arn
  port = 80
  protocol = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port = "443"
      protocol = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}