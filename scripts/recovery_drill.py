"""Exercise real local processes: healthy v1, failed v2 readiness, restored v1."""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def start(port, version, fail=False):
    env = {**os.environ, "APP_VERSION": version, "APP_FAIL_READINESS": str(fail).lower()}
    process = subprocess.Popen([sys.executable, "-m", "app.server", "--port", str(port)], cwd=ROOT, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("App exited during startup")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.3) as response:
                    if response.status == 200:
                        return process
            except (OSError, urllib.error.URLError):
                time.sleep(0.05)
        raise RuntimeError("App did not start")
    except Exception:
        stop(process)
        raise


def stop(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        with error:
            return error.code, json.load(error)


def drill():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    events = []
    for version, fail, expected in [("stable-v1", False, 200), ("broken-v2", True, 503), ("stable-v1", False, 200)]:
        process = start(port, version, fail)
        try:
            status, readiness = get(port, "/readyz")
            assert status == expected, (status, expected)
            assert readiness["version"] == version
            live, _ = get(port, "/healthz")
            assert live == 200
            events.append({"release": version, "readiness": status, "liveness": live,
                           "decision": "reject release" if fail else "accept release"})
        finally:
            stop(process)
    return {"result": "passed", "scope": "actual local Python processes; not AWS ECS", "events": events}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    report = drill()
    text = json.dumps(report, indent=2) + "\n"
    print(text)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
