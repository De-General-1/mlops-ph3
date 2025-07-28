terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

resource "aws_iam_role" "ecs_execution_role" {
  name = "${var.ecs_service_name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "${var.ecs_service_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}


resource "aws_ecs_cluster" "this" {
  name = var.ecs_cluster_name

  setting {
    name  = "containerInsights"
    value = var.container_insights_enabled
  }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name = aws_ecs_cluster.this.name

  capacity_providers = ["FARGATE"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}


resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = var.log_group_name 
  retention_in_days = 1
}

resource "aws_ecs_task_definition" "this" {
  family = var.ecs_td_family
  requires_compatibilities = ["FARGATE"]
  cpu       = var.cpu_size
  memory    = var.mem_size
  network_mode = "awsvpc"
  execution_role_arn = aws_iam_role.ecs_execution_role.arn
  task_role_arn = aws_iam_role.ecs_task_role.arn
  
  container_definitions = jsonencode([
    {
      name      = var.task_name
      image     = var.image_uri
      essential = true
      environment = var.environment_variables

       logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.log_group_name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = var.ecs_service_name
        }
      }
      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.host_port
        }
      ],
    }
  ])
}

resource "aws_ecs_service" "this" {
  name            = var.ecs_service_name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type = "FARGATE"
  

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = var.task_name
    container_port   = var.container_port
  }

  network_configuration {
    assign_public_ip = var.assign_public_ip
    subnets = var.ecs_service_subnets
    security_groups = var.ecs_service_sg
  } 

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [ var.alb_https_listener_arn, var.alb_http_listener_arn ]
}

