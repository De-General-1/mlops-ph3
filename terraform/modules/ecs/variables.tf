variable "ecs_cluster_name" {
  type = string
}

variable "container_insights_enabled" {
  type = string
}

variable "ecs_td_family" {
  type = string
}

variable "cpu_size" {
  type = number
  description = "the amount of vcpu to allocate to the task"
}

variable "mem_size" {
  type = number
  description = "the amount of memory to allocate to the task"
}

variable "container_port" {
  type = number
}

variable "host_port" {
  type = number
}

variable "task_name" {
  type = string
}

variable "image_uri" {
  type = string
}

variable "ecs_service_name" {
  description = "Name of the ECS service"
  type        = string
}

variable "desired_count" {
  description = "Number of desired tasks"
  type        = number
}

variable "assign_public_ip" {
  description = "Assign public IP to ECS service"
  type        = bool
}

variable "ecs_service_subnets" {
  description = "List of subnet IDs for ECS service"
  type        = list(string)
}

variable "ecs_service_sg" {
  type = list(string)
  description = "List of security group IDs for ECS service"
}

variable "environment_variables" {
description = "List of environment variables for the container"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "log_group_name" {
  description = "CloudWatch log group name"
  type        = string
  default     = ""
}

variable "aws_region" {
  
}

variable "target_group_arn" {
  
}

variable "elb_name" {
  
}

variable "alb_http_listener_arn" {
  
}

variable "alb_https_listener_arn" {
  
}