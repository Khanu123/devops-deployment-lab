from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import threading
import time
from collections import Counter
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .triage import load_alerts, triage

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("devops_lab")


class Application:
    def __init__(self, data_path=None, version=None, fail_readiness=False):
        self.version = version or os.getenv("APP_VERSION", "local")
        self.fail_readiness = fail_readiness
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.requests = Counter()
        self.alerts = load_alerts(data_path or ROOT / "sample_data" / "alerts.json")
        self.cases = triage(self.alerts)

    def record(self, status):
        with self.lock:
            self.requests[status] += 1

    def metrics(self):
        with self.lock:
            counts = dict(self.requests)
        lines = ["# TYPE lab_requests_total counter"]
        lines += [f'lab_requests_total{{status="{s}"}} {n}' for s, n in sorted(counts.items())]
        lines += ["# TYPE lab_uptime_seconds gauge", f"lab_uptime_seconds {time.monotonic() - self.started:.2f}",
                  "# TYPE lab_cases gauge", f"lab_cases {len(self.cases)}"]
        return "\n".join(lines) + "\n"

    def dashboard(self):
        cards = "".join(
            f'<article><div class="case-top"><span class="severity {escape(str(c["top_severity"]))}">{escape(str(c["top_severity"]))}</span>'
            f'<strong>{c["priority"]}<small> priority</small></strong></div>'
            f'<h3>{escape(str(c["host"]))}</h3><p class="muted">{escape(str(c["source_ip"]))} &middot; {c["alert_count"]} alerts</p>'
            f'<p>{escape(str(c["tactics"]))}</p><p class="mitre">{escape(str(c["mitre"]))}</p>'
            f'<div class="action">{escape(str(c["recommended_action"]))}</div></article>'
            for c in self.cases
        )
        return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sentinel | DevOps Deployment Lab</title><link rel="stylesheet" href="/style.css"></head><body>
<header><a class="brand" href="/">SENTINEL <span>/ deployment lab</span></a><span class="pill">SYNTHETIC DATA</span></header>
<main><div class="eyebrow">SECURITY OPERATIONS &times; DEVOPS</div><h1>From alerts to action.</h1>
<p class="intro">A container-ready SOC dashboard with automated delivery, health checks and observable operations.</p>
<div class="stats"><div><strong>{len(self.alerts)}</strong><span>Sample alerts</span></div><div><strong>{len(self.cases)}</strong><span>Prioritised cases</span></div>
<div><strong>{sum(c['priority'] >= 90 for c in self.cases)}</strong><span>Escalation candidates</span></div><div><strong class="version">{escape(self.version)}</strong><span>Running release</span></div></div>
<section class="section-title"><h2>Analyst queue</h2><a href="/api/cases">View JSON &rarr;</a></section><div class="grid">{cards}</div>
<section class="operations"><h2>Built to be operated</h2><div><a href="/healthz">Liveness</a><a href="/readyz">Readiness</a><a href="/metrics">Prometheus metrics</a><a href="/version">Release metadata</a></div>
<p>Read-only learning environment. No live SIEM connection or real incident data.</p></section></main><footer>Umar Khan Muhammad &middot; DevOps / DevSecOps portfolio</footer></body></html>'''


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DevOpsLab"
        sys_version = ""

        def do_GET(self):
            self.respond(False)

        def do_HEAD(self):
            self.respond(True)

        def respond(self, head):
            started = time.monotonic()
            path = urlsplit(self.path).path
            status, kind = 200, "application/json; charset=utf-8"
            if path == "/":
                body, kind = app.dashboard(), "text/html; charset=utf-8"
            elif path == "/style.css":
                body, kind = (ROOT / "app" / "style.css").read_text(encoding="utf-8"), "text/css; charset=utf-8"
            elif path == "/healthz":
                body = json.dumps({"status": "alive"})
            elif path == "/readyz":
                status = 503 if app.fail_readiness else 200
                body = json.dumps({"status": "not_ready" if app.fail_readiness else "ready", "version": app.version})
            elif path == "/version":
                body = json.dumps({"version": app.version})
            elif path == "/api/cases":
                body = json.dumps({"synthetic": True, "alert_count": len(app.alerts), "cases": app.cases})
            elif path == "/metrics":
                body, kind = app.metrics(), "text/plain; version=0.0.4; charset=utf-8"
            else:
                status, body = 404, json.dumps({"error": "not_found"})
            data = body.encode("utf-8")
            self.send_response(status)
            for key, value in {
                "Content-Type": kind, "Content-Length": str(len(data)), "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'",
            }.items():
                self.send_header(key, value)
            self.end_headers()
            if not head:
                self.wfile.write(data)
            app.record(status)
            LOG.info(json.dumps({"event": "request", "path": path if path in {"/", "/style.css", "/healthz", "/readyz", "/version", "/api/cases", "/metrics"} else "unknown",
                                 "status": status, "duration_ms": round((time.monotonic() - started) * 1000, 2), "version": app.version}))

        def log_message(self, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("APP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "8080")))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app = Application(fail_readiness=os.getenv("APP_FAIL_READINESS", "false").lower() == "true")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    server.timeout = 1
    stopping = threading.Event()
    def stop(*_):
        stopping.set()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    LOG.info(json.dumps({"event": "startup", "version": app.version, "port": args.port}))
    try:
        while not stopping.is_set():
            server.handle_request()
    finally:
        server.server_close()
        LOG.info(json.dumps({"event": "shutdown", "version": app.version}))


if __name__ == "__main__":
    main()
