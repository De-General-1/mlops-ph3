
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

resource "aws_instance" "this" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.security_group_ids
  user_data              = var.user_data
  iam_instance_profile   = var.iam_instance_profile
  
  ebs_block_device {
    device_name = "/dev/sda1"
    volume_size = 30
  }

  tags = merge(var.tags, {
    Name = var.tags["Name"]
  })
}
