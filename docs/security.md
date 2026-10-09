# Security model and tradeoffs

## Implemented controls

- Synthetic read-only data; no upload endpoint or live account integration.
- Explicit route allowlist; arbitrary files and traversal paths return 404.
- Escaped application data in HTML, restrictive CSP, no inline JavaScript, anti-framing and content-type headers.
- Structured logs avoid user-controlled query strings, raw request headers and payloads.
- Non-root UID/GID 10001, read-only root filesystem and dropped Linux capabilities.
- Local container port bound to loopback; app defaults to loopback outside Docker.
- Separate AWS task and execution roles. The application task has no AWS API policy. The execution role accesses only the named ECR repository and log group, with unavoidable wildcard ECR authentication.
- GitHub OIDC trust bound to the exact repository and `devops-lab` environment. Release permissions allow named ECR operations, update of the named ECS service, and passing only the two named task roles to ECS.
- Immutable full-SHA ECR tags and digest-pinned ECS images. No production `latest` deployment.
- Private, encrypted, versioned S3 state; TLS-only bucket policy and native lock files.
- ALB client CIDR restriction and application ingress only from the ALB security group. No SSH ingress.
- Commit-pinned third-party GitHub Actions; Dependabot updates are configured. The Docker base tag is rebuilt with `--pull`; release digests make deployed images immutable.

## Scan behaviour

CI blocks leaked secrets and fixable HIGH/CRITICAL vulnerabilities in the image. The scan's `ignore-unfixed` setting excludes vulnerabilities without a published fix from the blocking gate; it does not establish that the image contains zero vulnerabilities. Findings should be reviewed in scan artifacts. There are no third-party Python app dependencies to audit.

Terraform configuration scanning is **advisory** and saved as a CI artifact. It is not described as a passing security gate. This lab deliberately uses public task IPs, a restricted HTTP option, default AWS encryption keys, short log retention and no WAF/access-log bucket. Such findings need judgement and would require changes for production. See the actual `iac-scan.json` report and [validation](validation.md).

## Limits and production changes

The built-in Python HTTP server is used for a small synthetic learning application. It is not a production web server and has no application authentication, rate limiting or load-test evidence. A production service should use an appropriate server/framework and authentication, validated request limits, TLS, private subnets, strong egress controls, WAF/access logs where needed, managed encryption keys, backup policies and multiple tasks.

One ECS task is the cost-conscious lab default. During a rolling release, ECS may run a second task. Two subnet availability zones support the ALB; they do not make one task highly available. The ECS circuit breaker can restore only a previously completed deployment, and first deployment failures may have no rollback target.

`ecs:RegisterTaskDefinition` and `ecs:DescribeTaskDefinition` lack resource-level scoping in the release policy. Passing runtime roles and updating services are scoped. An operator with repository/environment release privileges can still publish code and influence that service. Protect `main`, review workflow changes, use environment branch restrictions and reviewer approvals where available.

Terraform plans and state may contain sensitive infrastructure metadata. They are ignored in Git. Bootstrap state is intentionally local and must be preserved securely. No GitHub workflow has state-bucket access or infrastructure-management permissions.
