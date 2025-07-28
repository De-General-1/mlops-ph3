terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

data "template_file" "mlflow_user_data" {
  template = file("${path.module}/templates/mlflow_user_data.sh")
}

data "template_file" "model_train_user_data" {
  template = file("${path.module}/templates/model_train_user_data.sh")
  vars = {
    ecr_image = var.ecr_repo_name
    mflow_server_ip = var.mflow_server_ip
  }
}

data "aws_ami_ids" "ubuntu_24" {
  owners = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20250610"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}