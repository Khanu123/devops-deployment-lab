# Operations and recovery runbook

## Service objectives for this lab

Readiness returns 200, the expected release identifier is visible, and the sample API returns 5 cases from 8 alerts. This is a demonstration target, not a measured production SLA.

## Local checks

```bash
python scripts/smoke_test.py http://127.0.0.1:8080
docker compose ps
docker compose logs --tail=50 dashboard
```

`/healthz` shows that the process responds. `/readyz` shows that it is ready to receive traffic. A process can be alive while unready; deployment decisions must use readiness.

## Incident: new release becomes unready

1. Check `/readyz`, `/version`, the ECS service deployment events, and target health.
2. Correlate the failing release SHA with its GitHub run and image digest. Inspect structured CloudWatch request logs and startup events.
3. Allow the ECS circuit breaker to reject failing tasks. Confirm the previous deployment is healthy; on a first-ever deployment there may be no successful revision to restore.
4. If automatic recovery does not restore service, run **Roll back AWS release** using a previously verified full release SHA.
5. Confirm the requested task definition is the primary completed ECS deployment. The release helper performs this check and fails on unexpected rollback.
6. From the allowed client IP, run the HTTP smoke test with the expected version. Check CloudWatch health metrics and the alarm state.
7. Document the cause, evidence, fix and follow-up test. Do not claim recovery based only on a green GitHub job or liveness endpoint.

Useful AWS commands (add `--region` if not configured):

```bash
aws ecs describe-services --cluster devops-lab --services devops-lab
aws logs tail /ecs/devops-lab --since 10m
aws cloudwatch describe-alarms --alarm-name-prefix devops-lab
```

## Reproduce the failure locally

```bash
python scripts/recovery_drill.py --output reports/local-recovery.json
docker build --build-arg APP_VERSION=ci -t devops-lab:ci .
bash scripts/container_drill.sh
```

The Python drill exercises a healthy process, intentionally unready release, and restored healthy process. The Docker drill keeps a stable container running while it rejects an unhealthy candidate. These are different scopes; neither is evidence that ECS rollback was executed in AWS.

## Other symptoms

| Symptom | Investigation and action |
| --- | --- |
| ALB request times out | Check your current public IP against `allowed_cidr`, DNS, listener and client protocol |
| `CannotPullContainerError` | Verify immutable digest exists, task execution role, HTTPS egress, subnet routes and public IP assignment |
| No logs | Check execution role log permissions and `/ecs/devops-lab`; app logs are stdout/stderr JSON |
| Terraform state lock | Confirm no legitimate operation is running before force-unlocking; preserve state versions |
| OIDC access denied | Check exact repository/environment trust, main-only environment rules and role ARN |
| Image tag already exists | Reuse the existing SHA tag or commit a new release; immutable tags are intentional |
| Unhealthy-target alarm | Review task readiness, deployment events and ALB target health; missing metrics are not proof of health |
| HTTP 404 | Check endpoint spelling; arbitrary paths and filesystem downloads are intentionally unavailable |

## Incident record template

```text
Release SHA and digest:
Detection time and symptom:
Affected validation checks:
Deployment events and log evidence:
Recovery action / known-good release:
Verified ECS revision and HTTP version:
Root cause:
Preventive change and test:
```
