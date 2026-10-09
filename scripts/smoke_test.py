"""Check an actual HTTP deployment and optionally assert its release identifier."""
import argparse
import json
import sys
import urllib.request


def check(base_url, expected_version=None):
    results = []
    for path in ("/healthz", "/readyz", "/version", "/api/cases", "/metrics", "/"):
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=10) as response:
            body = response.read().decode()
            assert response.status == 200, (path, response.status)
            if path == "/version" and expected_version:
                assert json.loads(body)["version"] == expected_version, "Unexpected release"
            if path == "/api/cases":
                payload = json.loads(body)
                assert payload["synthetic"] and payload["cases"], "Missing sample cases"
            if path == "/metrics":
                assert "lab_cases" in body, "Missing metrics"
            results.append({"path": path, "status": response.status})
    return {"result": "passed", "checks": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--version")
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.url, args.version), indent=2))
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
