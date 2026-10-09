mock_provider "aws" {}

override_resource {
  target          = aws_security_group.alb
  override_during = plan
  values          = { id = "sg-0123456789abcdef0" }
}
override_resource {
  target          = aws_iam_role.execution
  override_during = plan
  values          = { arn = "arn:aws:iam::123456789012:role/devops-lab-execution" }
}
override_resource {
  target          = aws_iam_role.task
  override_during = plan
  values          = { arn = "arn:aws:iam::123456789012:role/devops-lab-task" }
}

override_data {
  target = data.aws_availability_zones.available
  values = { names = ["eu-west-2a", "eu-west-2b"] }
}
override_data {
  target = data.aws_ecr_repository.app
  values = { arn = "arn:aws:ecr:eu-west-2:123456789012:repository/devops-lab" }
}

variables {
  image_uri    = "123456789012.dkr.ecr.eu-west-2.amazonaws.com/devops-lab@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  app_version  = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  allowed_cidr = "203.0.113.10/32"
}

run "secure_lab_topology" {
  command = plan
  assert {
    condition     = length(aws_subnet.public) == 2
    error_message = "ALB needs two availability zones."
  }
  assert {
    condition     = aws_ecs_service.app.deployment_circuit_breaker[0].rollback
    error_message = "Failed deployments must roll back."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.app.from_port == 8080 && aws_vpc_security_group_ingress_rule.app.referenced_security_group_id == aws_security_group.alb.id
    error_message = "App ingress must be limited to the ALB."
  }
  assert {
    condition     = jsondecode(aws_ecs_task_definition.app.container_definitions)[0].readonlyRootFilesystem
    error_message = "Container root filesystem must be read only."
  }
  assert {
    condition     = aws_cloudwatch_log_group.app.retention_in_days == 7
    error_message = "Log retention must remain bounded."
  }
}

run "reject_open_ingress" {
  command = plan
  variables {
    allowed_cidr = "0.0.0.0/0"
  }
  expect_failures = [var.allowed_cidr]
}

run "reject_mutable_image" {
  command = plan
  variables {
    image_uri = "123456789012.dkr.ecr.eu-west-2.amazonaws.com/devops-lab:latest"
  }
  expect_failures = [var.image_uri]
}

run "https_requires_domain" {
  command = plan
  variables {
    certificate_arn = "arn:aws:acm:eu-west-2:123456789012:certificate/example"
  }
  expect_failures = [var.domain_name]
}
