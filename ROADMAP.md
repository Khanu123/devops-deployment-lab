# Roadmap

## Implemented

- Read-only SOC web service and release/health/metrics endpoints.
- Docker packaging, hardened local Compose configuration and resource limits.
- Application and deployment regression tests.
- Real-process recovery and Linux Docker candidate-rejection drills.
- Terraform bootstrap/runtime stacks, state configuration and mocked infrastructure tests.
- GitHub CI, manual OIDC image publication/deployment and image rollback workflows.
- CloudWatch logs, dashboard and alarm configuration.
- Screenshots, evidence guide, employer review, case study, interview notes and teardown guidance.

## Account-dependent validation

- Provision AWS resources and verify the first immutable image deployment.
- Confirm DNS/TLS where configured and run HTTP smoke checks from an allowed client IP.
- Confirm SNS subscription and test actual alarm delivery.
- Exercise live ECS automatic rollback and manual rollback; attach actual evidence.
- Complete main-stack teardown and inspect billing/resource cleanup.

## Optional extensions

- Production server/framework and authentication.
- Multiple tasks, private subnets/endpoints and autoscaling.
- A deployed Prometheus/Grafana stack instead of only exposing metrics.
- Load tests, service-level objectives and a cloud cost report.
