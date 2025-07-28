terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

resource "aws_security_group" "this" {
  name = "ecs-service-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port                = 8000
    to_port                  = 8000
    protocol                 = "tcp"
    security_groups          = [module.inference_alb_sg.security_group_id]
  }

}