# Costs and teardown

This lab has no free-running cloud deployment in its initial evidence. Local Python and Docker execution do not create AWS resources.

## Before creating resources

Use the [AWS Pricing Calculator](https://calculator.aws/) for your actual region and duration. Do not assume this project fits a free tier. Chargeable components include the ALB and capacity units, Fargate vCPU/memory, public IPv4 addresses, ECR image storage/scanning where applicable, CloudWatch logs/metrics/alarms/dashboard, S3 storage/requests, SNS delivery and data transfer. Exact amounts depend on region, account offers, traffic and current prices.

Suggested lab controls:

- Set an AWS Budget notification before provisioning; it is an alert, not a spending cap.
- Run the lab for a short learning session and destroy the main infrastructure afterwards.
- Keep the default 0.25 vCPU / 0.5 GiB task and one desired task unless you have a reason to change them.
- Avoid adding a NAT gateway simply to imitate a larger production design without estimating its cost.
- Logs retain seven days. ECR images remain until explicitly removed so rollback stays possible.
- Scaling the service to zero does not remove ALB, public IP, storage or monitoring charges.

## Destroy the main stack

Use the same backend and variable file as the creation session:

```bash
terraform -chdir=infra/main plan -destroy -out=destroy.tfplan
terraform -chdir=infra/main apply destroy.tfplan
```

Inspect the destroy plan before applying it. It covers the dedicated VPC, subnets, routes, load balancer, service/task configuration, runtime IAM, logs, dashboard, alarms and SNS resources. It does not destroy unrelated account resources.

Check AWS afterwards for resources tagged `Project=devops-lab`, lingering ECS tasks, ECR storage and public IP charges. Preserve state until you confirm cleanup.

## Bootstrap remains intentionally protected

Bootstrap includes the ECR repository, GitHub release role/OIDC provider and state bucket. ECR uses `force_delete=false`; the state bucket uses `prevent_destroy=true` and contains versioned state. Main-stack destruction leaves these in place so state remains recoverable.

If retiring the lab completely, first finish main-stack teardown, archive necessary state securely, remove only this lab's ECR images, and explicitly retire the bootstrap resources. Deleting a versioned bucket requires removing all versions and delete markers; do not remove state while infrastructure still exists. Remove the bucket's Terraform deletion guard only as part of this deliberate final retirement. Never delete a shared GitHub OIDC provider; an existing provider passed through `existing_oidc_provider_arn` is not managed by this stack.

Also remove the repository's AWS environment variables and release access if you no longer use the lab. Docker cleanup is simply `docker compose down`; the Docker drill cleans up its own two named containers.
