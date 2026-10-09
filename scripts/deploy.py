"""Deploy an immutable image; reject ECS automatic rollback masquerading as success."""
import argparse
import copy
import json
import re
import subprocess
import sys

TASK_FIELDS = {"family", "taskRoleArn", "executionRoleArn", "networkMode", "containerDefinitions", "volumes",
               "placementConstraints", "requiresCompatibilities", "cpu", "memory", "pidMode", "ipcMode",
               "proxyConfiguration", "inferenceAccelerators", "ephemeralStorage", "runtimePlatform"}


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"], text=True))


def prepare_task(task, image, version):
    if task.get("family") != "devops-lab":
        raise ValueError("Refusing to modify a different task family")
    if not re.fullmatch(r"[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/devops-lab@sha256:[a-f0-9]{64}", image):
        raise ValueError("Expected an immutable devops-lab ECR image digest")
    if not re.fullmatch(r"[a-f0-9]{40}", version):
        raise ValueError("Expected a full Git SHA as release version")
    cleaned = copy.deepcopy({key: value for key, value in task.items() if key in TASK_FIELDS})
    dashboards = [c for c in cleaned["containerDefinitions"] if c["name"] == "dashboard"]
    if len(dashboards) != 1:
        raise ValueError("Expected exactly one dashboard container")
    container = dashboards[0]
    container["image"] = image
    container["environment"] = [item for item in container.get("environment", []) if item["name"] not in {"APP_VERSION", "APP_FAIL_READINESS"}]
    container["environment"].append({"name": "APP_VERSION", "value": version})
    return cleaned


def validate_rollout(service, expected):
    primary = [d for d in service.get("deployments", []) if d["status"] == "PRIMARY"]
    if len(primary) != 1 or primary[0]["taskDefinition"] != expected or primary[0].get("rolloutState") != "COMPLETED":
        raise RuntimeError("Requested revision did not complete; ECS may have rolled back")
    if service.get("runningCount", 0) < 1:
        raise RuntimeError("Service has no running task")


def deploy(image, version):
    service = aws("ecs", "describe-services", "--cluster", "devops-lab", "--services", "devops-lab")
    if service.get("failures") or len(service["services"]) != 1:
        raise RuntimeError("Provision infra/main before deploying the service")
    current = service["services"][0]["taskDefinition"]
    task = aws("ecs", "describe-task-definition", "--task-definition", current)["taskDefinition"]
    requested = prepare_task(task, image, version)
    registered = aws("ecs", "register-task-definition", "--cli-input-json", json.dumps(requested))
    target = registered["taskDefinition"]["taskDefinitionArn"]
    aws("ecs", "update-service", "--cluster", "devops-lab", "--service", "devops-lab", "--task-definition", target)
    subprocess.run(["aws", "ecs", "wait", "services-stable", "--cluster", "devops-lab", "--services", "devops-lab"], check=True)
    after = aws("ecs", "describe-services", "--cluster", "devops-lab", "--services", "devops-lab")["services"][0]
    validate_rollout(after, target)
    return {"result": "passed", "previous_task_definition": current, "task_definition": target, "image": image, "version": version,
            "scope": "ECS service steady state and exact revision; HTTP smoke test must run from an allowed client IP"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(deploy(args.image, args.version), indent=2))
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Deployment failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
