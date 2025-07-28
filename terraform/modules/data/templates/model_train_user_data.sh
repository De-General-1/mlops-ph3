#!/bin/bash
set -xe

REGION="us-east-1"
ECR_IMAGE="${ecr_image}"
MFLOW_SERVER_IP="${mflow_server_ip}"

# Install dependencies
apt-get update -y
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    unzip

# Install Docker (official method for Ubuntu 24+)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start Docker
systemctl enable docker
systemctl start docker

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install
rm -rf awscliv2.zip aws/

# ECR login
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin $${ECR_IMAGE%/*}

# Pull and run the image
docker pull $ECR_IMAGE
docker run -d --name model_train_image $ECR_IMAGE
