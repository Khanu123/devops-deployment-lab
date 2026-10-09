# Interview notes

## Explain the project

"I took the synthetic SOC triage logic from my Python project and built a DevOps lab around it: a containerised web service, GitHub Actions verification, Terraform AWS infrastructure, OIDC image publishing, monitoring and release recovery. I tested the app, local recovery, containers and mock infrastructure. Live AWS deployment is a documented account-dependent step, so I distinguish implemented cloud configuration from deployed cloud experience."

## Questions to prepare for

| Question | Key points |
| --- | --- |
| What is CI versus CD here? | CI tests and scans without AWS; manual delivery publishes a digest-pinned image and updates a service |
| Why separate readiness and liveness? | The broken release is alive but should receive no traffic; readiness rejects it |
| Why OIDC? | Short-lived federated credentials avoid stored long-lived access keys; trust is restricted to one environment |
| What owns release state? | Terraform owns infrastructure; the pipeline owns the ECS service's task-definition revision |
| How do you know deployment succeeded? | Exact requested primary task definition, completed rollout, running task count, then client-side HTTP smoke/version check |
| Why pin images to digests? | A deployment references exact content, and immutable SHA tags identify retained rollback candidates |
| What does mock Terraform testing prove? | Configuration constraints and planned relationships; it does not prove live API permissions, quotas or provisioning |
| Is this highly available? | No: one desired task is a lab cost tradeoff despite two ALB availability zones |
| What remains for production? | Server hardening, authentication, default TLS, private network design, availability, load testing and operational evidence |
| What did the recovery drill actually do? | Python processes fail/recover; Docker rejects a candidate while retaining stable service; ECS rollback was not executed |

## CV wording after checking the evidence

"Built a DevOps/DevSecOps deployment lab around a Python SOC dashboard using Docker, GitHub Actions and Terraform; implemented AWS ECS/ECR/ALB configuration, OIDC release workflows, health checks, monitoring and recovery runbooks, with automated application, container and infrastructure validation."

Do not change "implemented AWS configuration" into "deployed to AWS" until you have actually provisioned and verified it.
