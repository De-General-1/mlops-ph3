variable "ami_id" {
  description = "AMI ID to use for the EC2 instance"
  type        = string
}

variable "instance_type" {
  description = "Instance type for EC2"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "Name of the SSH key pair"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID to launch the EC2 instance in"
  type        = string
}

variable "security_group_ids" {
  description = "List of security group IDs to associate with the EC2 instance"
  type        = list(string)
}

variable "iam_instance_profile" {
  description = "value for the iam_instance_profile"
  type        = string
}

variable "user_data" {
  description = "User data script to provision the instance (e.g., install Docker and run a container)"
  type        = string
  default     = <<-EOF
    #!/bin/bash

    set -e

    # Update and upgrade system packages
    apt update -y
    apt upgrade -y

    # Install Docker
    if ! command -v docker &> /dev/null; then
      curl -fsSL https://get.docker.com -o get-docker.sh
      sh get-docker.sh
      rm get-docker.sh
    fi

    # Start and enable Docker service
    systemctl start docker
    systemctl enable docker

    # Add current user to the docker group (non-root Docker use)
    usermod -aG docker ubuntu

    # Run nginx container in detached mode
    docker run -d -p 80:80 nginx
  EOF
}


variable "tags" {
  description = "A map of tags to apply to the instance"
  type        = map(string)
  default     = {}
}
