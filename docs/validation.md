# Validation evidence

Initial checks were run on 10 October 2026. The [verified GitHub CI run](https://github.com/Khanu123/devops-deployment-lab/actions/runs/38005804206) passed all three jobs at commit `54c4f7e894667540b04a1c62dc137a2138634a0f`; its [run record](../reports/verified-ci/run.json) and actual artifacts are committed under `reports/verified-ci/`. Evidence is recorded by scope; implemented AWS configuration is not described as an executed cloud deployment.

| Check | Scope | Result / evidence |
| --- | --- | --- |
| 20 Python tests | Triage, actual HTTP server requests, HTML escaping, routes, readiness and deployment regression logic | Passed locally; CI reruns on Linux |
| Process recovery | Actual healthy, broken and restored Python processes | Passed: [record](../reports/process-recovery.json) |
| Desktop/mobile browser review | Headless Edge, real local HTTP app, 5 cards, no page errors or mobile horizontal overflow | Passed: [record](../reports/browser-checks.json), [desktop](screenshots/dashboard-desktop.png), [mobile](screenshots/dashboard-mobile.png) |
| Terraform format and validate | Both roots, actual installed locked AWS provider schema | Passed locally |
| Terraform main mock tests | Topology, rollback setting, read-only filesystem, restricted ingress, immutable digest, HTTPS domain | 4 test runs passed |
| Terraform bootstrap mock tests | Immutable registry, private state, exact OIDC subject and audience | 1 test run passed |
| Linux Docker build and drill | Actual Linux containers on GitHub Actions | Passed: [Docker smoke](../reports/verified-ci/container-smoke.json) and [recovery](../reports/verified-ci/container-recovery.json) |
| Container/secret scans | Trivy gates on GitHub Actions | Passed: [image scan](../reports/verified-ci/image-scan.json) and [secret scan](../reports/verified-ci/secret-scan.json) |
| IaC scan | Advisory Trivy configuration findings | 14 advisory findings: [actual report](../reports/verified-ci/iac-scan.json); see security tradeoffs |
| Live AWS service/alarms/rollback | Actual account deployment | Not executed; account configuration required |

## Reproduce

```bash
python -m unittest discover -s tests -v
python scripts/recovery_drill.py --output reports/local-recovery.json
terraform fmt -check -recursive infra
terraform -chdir=infra/bootstrap init -backend=false -lockfile=readonly
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/bootstrap test
terraform -chdir=infra/main init -backend=false -lockfile=readonly
terraform -chdir=infra/main validate
terraform -chdir=infra/main test
docker build --build-arg APP_VERSION=ci -t devops-lab:ci .
bash scripts/container_drill.sh
```

The test files explicitly use `mock_provider "aws"`; their plans need no AWS credentials and create no AWS resources. Keep test-only evidence separate from a real plan/apply.

## CI artifacts

Open [GitHub Actions](https://github.com/Khanu123/devops-deployment-lab/actions/workflows/ci.yml), select a completed run and review:

- `application-evidence`: Python test log and process recovery JSON.
- `infrastructure-evidence`: schema validation, Terraform test logs and advisory IaC scan.
- `container-evidence`: HTTP smoke results, failed-candidate recovery record, structured logs, image scan and secret scan.

Cloud workflow artifacts are generated only when an authorised account release runs. Browser screenshots show a local application, not an AWS console or live cloud service.

## Scan interpretation

The image gate reports zero fixable HIGH/CRITICAL vulnerabilities for the tested image; this is a filtered result, not a claim of zero vulnerabilities of all severities. The secret scan reports zero detected secrets. The advisory infrastructure scan records 14 findings: customer-managed encryption keys, bucket access logging, log encryption, Container Insights, internet-facing ALB, the optional HTTP listener, SNS encryption, broad HTTPS egress, security-group-rule descriptions and VPC flow logs. These are preserved rather than suppressed.

The first CI run caught Linux provider checksums missing from the Windows-generated lock files and vulnerable packages bundled with unused Python installer tooling. Platform-specific checksums were recorded and the installer tooling was removed from the runtime image. The verified rerun passed without relaxing the container vulnerability gate.
