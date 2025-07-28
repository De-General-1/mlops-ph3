variable "vpc_cidr" {
  description = "CIDR block for the VPC (10.0.0.0/16 provides 65,536 IP addresses)"
  type        = string
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets across multiple AZs"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets across multiple AZs"
  type        = list(string)
}

variable "availability_zones" {
  description = "AWS availability zones in eu-west-1 region"
  type        = list(string)
}

variable "environment" {
  description = "value for the environment tag"
  type        = string
}

variable "inference_api_repo_name" {
  type        = string
  description = "ecr repository name for the inference api docker images"
}

variable "inference_api_images_to_keep" {
  type        = number
  description = "number of images to keep for the inference api"
}

variable "train_script_repo_name" {
  type        = string
  description = "ecr repository name for the inference api docker images"
}

variable "train_script_images_to_keep" {
  type        = number
  description = "number of images to keep for the inference api"
}

variable "evaluate_script_repo_name" {
  type        = string
  description = "ecr repository name for the inference api docker images"
}

variable "evaluate_script_images_to_keep" {
  type        = number
  description = "number of images to keep for the inference api"
}

variable "account_id" {
  type        = number
  description = "account id for the aws account where the resources are being provisioned"
}

variable "inference_container_port" {
  type = number
}

variable "inference_ecs_service_name" {
  type = string
}

variable "inference_api_domain_name" {
  type = string

}

variable "hosted_zone_id" {
  type = string
}

variable "inference_api_alb_name" {
  type = string
}