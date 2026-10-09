import contextlib
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.server import Application, make_handler


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.app = Application(version="test-v1")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, method="GET"):
        return urllib.request.urlopen(urllib.request.Request(self.url + path, method=method), timeout=3)

    def test_dashboard_has_real_case_counts_and_release(self):
        with self.request("/") as response:
            page = response.read().decode()
            self.assertIn("test-v1", page)
            self.assertIn("Analyst queue", page)
            self.assertIn(self.app.cases[0]["host"], page)

    def test_api_matches_triage_and_marks_synthetic_data(self):
        with self.request("/api/cases") as response:
            data = json.load(response)
        self.assertTrue(data["synthetic"])
        self.assertEqual(data["cases"], self.app.cases)
        self.assertEqual(data["alert_count"], 8)
        self.assertEqual(len(data["cases"]), 5)

    def test_readiness_failure_does_not_fail_liveness(self):
        self.app.fail_readiness = True
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/readyz")
        self.assertEqual(error.exception.code, 503)
        error.exception.close()
        with self.request("/healthz") as response:
            self.assertEqual(response.status, 200)

    def test_metrics_count_success_and_failure(self):
        with self.request("/healthz") as response:
            response.read()
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/missing")
        error.exception.close()
        with self.request("/metrics") as response:
            metrics = response.read().decode()
        self.assertIn('lab_requests_total{status="200"}', metrics)
        self.assertIn('lab_requests_total{status="404"}', metrics)
        self.assertIn("lab_cases 5", metrics)

    def test_paths_cannot_read_files(self):
        for path in ("/../Dockerfile", "/%2e%2e/Dockerfile", "/sample_data/alerts.json"):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.request(path)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()

    def test_head_and_security_headers(self):
        with self.request("/", "HEAD") as response:
            self.assertEqual(response.read(), b"")
            self.assertGreater(int(response.headers["Content-Length"]), 0)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_html_escapes_version_and_alert_fields(self):
        self.app.version = '<script>alert("x")</script>'
        self.app.cases[0]["host"] = '<img src=x onerror=alert(1)>'
        with self.request("/") as response:
            page = response.read().decode()
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img", page)
        self.assertIn("&lt;script&gt;", page)

    def test_unsupported_write_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/api/cases", "POST")
        self.assertEqual(error.exception.code, 501)
        error.exception.close()

    def test_invalid_data_fails_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text('[{"severity":"invalid"}]', encoding="utf-8")
            with self.assertRaises(ValueError):
                Application(data_path=path)


if __name__ == "__main__":
    unittest.main()
