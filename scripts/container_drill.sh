#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports
cleanup() { docker rm -f lab-stable lab-broken >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
docker run -d --name lab-stable --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 100 -p 127.0.0.1:8080:8080 devops-lab:ci
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/readyz >/dev/null; then break; fi
  sleep 1
done
python scripts/smoke_test.py http://127.0.0.1:8080 --version ci | tee reports/container-smoke.json
test "$(docker inspect --format '{{.Config.User}}' lab-stable)" = "10001:10001"
test "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' lab-stable)" = "true"
docker run -d --name lab-broken --read-only --cap-drop ALL --security-opt no-new-privileges -e APP_FAIL_READINESS=true -p 127.0.0.1:8081:8080 devops-lab:ci
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8081/healthz >/dev/null; then break; fi
  sleep 1
done
test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8081/readyz)" = "503"
if python scripts/smoke_test.py http://127.0.0.1:8081; then echo 'Broken release incorrectly accepted'; exit 1; fi
docker rm -f lab-broken
python scripts/smoke_test.py http://127.0.0.1:8080 --version ci
printf '{"result":"passed","scope":"Docker candidate rejection; stable container kept running","broken_readiness":503,"stable_readiness":200}\n' | tee reports/container-recovery.json
docker logs lab-stable >reports/container-logs.jsonl 2>&1
