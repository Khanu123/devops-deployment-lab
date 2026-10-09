# Case study: taking a SOC tool into a DevOps workflow

## Problem

My existing Sentinel SOC Dashboard demonstrated Python triage logic and reporting. A reviewer could inspect outputs, but it did not demonstrate how I would package a service, verify a release, manage cloud infrastructure or respond to an unhealthy deployment.

## Implementation

I adapted the synthetic triage engine into a read-only HTTP application with a responsive analyst queue, JSON API, release endpoint, separate liveness/readiness checks, structured logs and Prometheus-format metrics. The sample dataset remains 8 alerts and 5 cases.

Docker packages the app with a non-root user and a health check. Compose makes local execution repeatable and limits resources. CI exercises Python behaviour, real HTTP requests, actual process recovery, Linux Docker candidate rejection, image/secret scans and Terraform mock plans.

The Terraform bootstrap separates registry, state and delivery identity from the runtime stack. The main stack defines a dedicated VPC, two subnets, ALB, ECS Fargate service, scoped IAM and CloudWatch monitoring. GitHub workflows publish immutable images using OIDC, deploy service revisions, or restore a known-good image.

## Failure and diagnosis

The controlled broken release keeps `/healthz` at 200 while `/readyz` returns 503. This shows why process availability alone is insufficient to accept a release. The local recovery script actually stops and starts distinct processes, records the failed candidate, and restores the stable release. The Docker drill keeps a stable container running while rejecting a candidate on a separate port.

The deployment helper also covers a less obvious failure: `aws ecs wait services-stable` can finish after AWS restores an older revision. The script checks that the primary deployment matches the requested task definition and reports `COMPLETED`; a healthy rollback is not mistaken for a successful new release. A regression test exercises this distinction.

## Evidence and boundaries

Actual local evidence lives in `reports/`, browser screenshots in `docs/screenshots/`, and Linux container/security/infrastructure evidence in GitHub Actions artifacts. [Validation](validation.md) distinguishes these scopes. AWS resources were not provisioned during initial project verification, so this case study does not claim a successful Fargate deployment or a real cloud incident.

## Tradeoffs

The lab uses a small standard-library server and one desired task. Public task IPs avoid NAT gateway costs while a security group blocks direct inbound traffic. HTTP is available only to a restricted client CIDR; an existing certificate/domain enables HTTPS. IaC scanning is advisory because these explicit learning choices do not meet every production rule.

## Next production steps

Use a production server and authentication, multiple tasks, private subnets and suitable AWS endpoints/egress, TLS by default, stronger logging and encryption controls, and load testing. Then execute the documented cloud deployment, alarm and rollback drills in an authorised AWS account and attach their actual evidence.
