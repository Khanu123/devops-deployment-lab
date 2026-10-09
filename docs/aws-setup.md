# AWS setup and first release

These are executable setup instructions. AWS provisioning and release workflows have not been exercised against a live account in this project's initial validation. Terraform tests use a mocked provider; they do not prove AWS quotas, IAM propagation, or live resource creation.

## Prerequisites

- A dedicated AWS learning account, billing visibility, and an authenticated AWS CLI v2 session (prefer IAM Identity Center / SSO).
- Terraform 1.13.5 and Docker with Linux containers.
- GitHub permission to configure repository environments and variables.
- Permission to create the bootstrap and main infrastructure, including initial ECS service-linked role creation.
- An actual public IPv4 address for your restricted client CIDR.

Review [costs and cleanup](costs-and-cleanup.md) before provisioning. No cloud workflow runs on a regular push.

## 1. Create the registry, state bucket and GitHub identity

```bash
aws sts get-caller-identity
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap plan -out=bootstrap.tfplan
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
terraform -chdir=infra/bootstrap output
```

Run the plan/apply from an authorised workstation. Bootstrap state remains local: preserve `infra/bootstrap/terraform.tfstate` securely outside Git. Do not commit plan files or state. If an OIDC provider already exists, copy `terraform.tfvars.example` to `terraform.tfvars`, set `existing_oidc_provider_arn`, and use it rather than creating a duplicate.

Bootstrap outputs include `state_bucket`, `ecr_repository_url` and `github_role_arn`. Names are fixed for a single lab per account/region.

## 2. Configure GitHub's deployment environment

In repository Settings > Environments, create **devops-lab**. Restrict deployment branches to **main**. Enable a required reviewer if your GitHub plan supports that environment feature. The OIDC trust is bound to this environment, so its branch rules matter.

Add environment variables (these are identifiers, not access-key secrets):

| Variable | Value |
| --- | --- |
| `AWS_REGION` | `eu-west-2`, or the chosen region |
| `AWS_ROLE_ARN` | Bootstrap `github_role_arn` |
| `ECR_REPOSITORY_URL` | Bootstrap `ecr_repository_url` |

No AWS access key or secret access key is stored in GitHub. The workflow assumes the release role with OIDC. That role cannot create network infrastructure, alter IAM policies, or read Terraform state; workstation Terraform owns those operations.

## 3. Publish the first image

In Actions, run **Publish or deploy to AWS** from `main` with mode **publish-only**. It runs the verification workflow, builds and scans the release image, pushes an immutable full-Git-SHA tag, and prints the digest URI and release SHA in its job summary.

The workflow reuses an existing immutable SHA tag when rerun. A change to the Dockerfile/base image should be committed to obtain a new release SHA. Images are intentionally retained for rollback.

## 4. Provision the service

Copy `infra/main/backend.hcl.example` to `infra/main/backend.hcl` and replace its bucket with the actual bootstrap output. Use the same AWS region in backend and provider configuration.

Copy `infra/main/terraform.tfvars.example` to `infra/main/terraform.tfvars` and fill in:

- `image_uri`: the immutable ECR digest URI from publish-only.
- `app_version`: the full SHA reported by that run.
- `allowed_cidr`: your own public IPv4 address followed by `/32`.
- Optional `alarm_email`: confirm the resulting SNS subscription.

```bash
terraform -chdir=infra/main init -backend-config=backend.hcl
terraform -chdir=infra/main plan -out=service.tfplan
terraform -chdir=infra/main apply service.tfplan
terraform -chdir=infra/main output
```

The main backend uses private encrypted S3 state with native lock files and versioning. It has no dependency on deprecated DynamoDB state locking.

For HTTPS, provide an existing ACM `certificate_arn` in the chosen region and its `domain_name`. After apply, create a DNS CNAME or Route 53 alias from that domain to `load_balancer_dns`. The HTTP listener redirects to HTTPS. TLS validation must use the certificate's domain, not the AWS ALB hostname.

Without a certificate, the lab uses HTTP restricted to your client CIDR. Serve synthetic data only. Do not broaden it to a public real-data dashboard.

## 5. Verify and operate

From your permitted client IP:

```bash
python scripts/smoke_test.py http://YOUR_ALB_DNS --version YOUR_FULL_RELEASE_SHA
aws logs tail /ecs/devops-lab --since 10m --region eu-west-2
aws ecs describe-services --cluster devops-lab --services devops-lab --region eu-west-2
```

If HTTPS is configured, use `https://YOUR_DOMAIN`. GitHub-hosted runners have changing public IPs and are intentionally not given inbound ALB access. The cloud release helper checks exact ECS revision and steady state; the HTTP smoke test is run separately from an allowed client. Neither check substitutes for the other.

Inspect the `devops-lab` CloudWatch dashboard and alarms. No alarm email can arrive until its SNS subscription is confirmed.

## Subsequent releases and rollback

Commit to `main`, then manually run **Publish or deploy to AWS** with **deploy**. It pushes a digest-pinned release, registers a new task revision based on the current service configuration, and verifies that the requested revision completed. It rejects the case where ECS automatically rolled back to an older healthy revision.

To restore a prior release, run **Roll back AWS release** with its known-good full Git SHA. It resolves the retained immutable ECR digest, updates release metadata, registers a new task revision and verifies it. See [runbook](runbook.md).

Terraform's ECS service ignores only `task_definition` changes because the pipeline owns release revisions. To change CPU, memory, container configuration, or initial image configuration, apply Terraform and then publish/deploy through the pipeline so the service picks up that new definition. Keep bootstrap and main state securely until teardown is complete.
