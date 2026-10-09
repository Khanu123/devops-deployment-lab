data "aws_availability_zones" "available" {
  state = "available"
}
data "aws_ecr_repository" "app" {
  name = "devops-lab"
}
resource "aws_vpc" "lab" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "devops-lab" }
}
resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id
}
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.lab.id
  cidr_block        = cidrsubnet(aws_vpc.lab.cidr_block, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_security_group" "alb" {
  name        = "devops-lab-alb"
  description = "Restricted lab clients reach the HTTP/HTTPS load balancer"
  vpc_id      = aws_vpc.lab.id
}
resource "aws_security_group" "app" {
  name        = "devops-lab-app"
  description = "Application receives traffic only from the load balancer"
  vpc_id      = aws_vpc.lab.id
}
resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = var.allowed_cidr
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}
resource "aws_vpc_security_group_ingress_rule" "https" {
  count             = var.certificate_arn == "" ? 0 : 1
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = var.allowed_cidr
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}
resource "aws_vpc_security_group_egress_rule" "alb" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
}
resource "aws_vpc_security_group_ingress_rule" "app" {
  security_group_id            = aws_security_group.app.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
}
# Public task IPs avoid a NAT gateway in this small lab; inbound is still ALB-only.
resource "aws_vpc_security_group_egress_rule" "app_https" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}
resource "aws_lb" "app" {
  name                       = "devops-lab"
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  drop_invalid_header_fields = true
}
resource "aws_lb_target_group" "app" {
  name                 = "devops-lab"
  port                 = 8080
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = aws_vpc.lab.id
  deregistration_delay = 15
  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"
  dynamic "default_action" {
    for_each = var.certificate_arn == "" ? [1] : []
    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.app.arn
    }
  }
  dynamic "default_action" {
    for_each = var.certificate_arn != "" ? [1] : []
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }
}
resource "aws_lb_listener" "https" {
  count             = var.certificate_arn == "" ? 0 : 1
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/devops-lab"
  retention_in_days = 7
}
locals {
  task_trust = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role" "execution" {
  name               = "devops-lab-execution"
  assume_role_policy = local.task_trust
}
resource "aws_iam_role_policy" "execution" {
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = data.aws_ecr_repository.app.arn },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" }
    ]
  })
}
# No AWS API permissions are granted to the application itself.
resource "aws_iam_role" "task" {
  name               = "devops-lab-task"
  assume_role_policy = local.task_trust
}
resource "aws_ecs_cluster" "lab" {
  name = "devops-lab"
}
resource "aws_ecs_task_definition" "app" {
  family                   = "devops-lab"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name            = "dashboard", image = var.image_uri, essential = true, user = "10001:10001", readonlyRootFilesystem = true
    portMappings    = [{ containerPort = 8080, protocol = "tcp" }]
    environment     = [{ name = "APP_VERSION", value = var.app_version }]
    linuxParameters = { capabilities = { drop = ["ALL"] } }
    healthCheck = {
      command  = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=2)"]
      interval = 15, timeout = 3, retries = 3, startPeriod = 15
    }
    logConfiguration = {
      logDriver = "awslogs"
      options   = { awslogs-group = aws_cloudwatch_log_group.app.name, awslogs-region = var.aws_region, awslogs-stream-prefix = "app" }
    }
  }])
}
resource "aws_ecs_service" "app" {
  name                               = "devops-lab"
  cluster                            = aws_ecs_cluster.lab.id
  task_definition                    = aws_ecs_task_definition.app.arn
  desired_count                      = 1
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 30
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  wait_for_steady_state              = true
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "dashboard"
    container_port   = 8080
  }
  depends_on = [aws_lb_listener.http, aws_lb_listener.https, aws_iam_role_policy.execution]
  # CI/CD owns release revisions; Terraform continues to own service infrastructure.
  lifecycle {
    ignore_changes = [task_definition]
  }
}
resource "aws_sns_topic" "alerts" {
  name = "devops-lab-alerts"
}
resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}
resource "aws_cloudwatch_metric_alarm" "unhealthy" {
  alarm_name          = "devops-lab-unhealthy-targets"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  dimensions          = { LoadBalancer = aws_lb.app.arn_suffix, TargetGroup = aws_lb_target_group.app.arn_suffix }
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "devops-lab-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  dimensions          = { ClusterName = aws_ecs_cluster.lab.name, ServiceName = aws_ecs_service.app.name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_dashboard" "lab" {
  dashboard_name = "devops-lab"
  dashboard_body = jsonencode({ widgets = [
    { type = "metric", x = 0, y = 0, width = 12, height = 6, properties = {
      title   = "ECS CPU and memory", region = var.aws_region, period = 60, stat = "Average"
      metrics = [["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.lab.name, "ServiceName", aws_ecs_service.app.name], [".", "MemoryUtilization", ".", ".", ".", "."]]
    } },
    { type = "metric", x = 12, y = 0, width = 12, height = 6, properties = {
      title   = "Healthy and unhealthy targets", region = var.aws_region, period = 60, stat = "Maximum"
      metrics = [["AWS/ApplicationELB", "HealthyHostCount", "LoadBalancer", aws_lb.app.arn_suffix, "TargetGroup", aws_lb_target_group.app.arn_suffix], [".", "UnHealthyHostCount", ".", ".", ".", "."]]
    } }
  ] })
}
