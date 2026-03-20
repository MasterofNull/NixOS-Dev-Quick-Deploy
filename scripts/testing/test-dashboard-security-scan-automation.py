#!/usr/bin/env python3
"""Regression for the dashboard/operator security scan automation."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class _StubHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Security-Policy", "default-src 'self'")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-RateLimit-Category", "default")
            self.send_header("X-RateLimit-Limit", "240")
            self.send_header("X-RateLimit-Remaining", "239")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path == "/api/insights/security/compliance":
            body = json.dumps(
                {
                    "controls": {
                        "content_security_policy": True,
                        "rate_limiting": True,
                        "operator_audit_log": True,
                        "tamper_evident_audit_sealing": True,
                        "dashboard_security_scan_automation": True,
                    },
                    "audit_integrity": {"valid": True, "sealed_events": 2},
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/audit/operator/integrity":
            body = json.dumps(
                {
                    "available": True,
                    "valid": True,
                    "seal_algorithm": "sha256-chain-v1",
                    "sealed_events": 2,
                    "legacy_events": 0,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dashboard-security-scan-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        port = _free_port()
        server = ThreadingHTTPServer(("127.0.0.1", port), _StubHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            report_path = tmp_path / "latest-dashboard-security-scan.json"
            subprocess.run(
                [
                    "bash",
                    str(ROOT / "scripts" / "security" / "dashboard-security-scan.sh"),
                    "--url",
                    f"http://127.0.0.1:{port}",
                    "--output",
                    str(report_path),
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            assert_true(report.get("status") == "ok", "scan report should be ok")
            assert_true(report.get("summary", {}).get("security_headers_present") is True, "security headers should be detected")
            assert_true(report.get("summary", {}).get("audit_integrity_valid") is True, "integrity should be valid")

            audit_dir = tmp_path / "security"
            audit_dir.mkdir(parents=True, exist_ok=True)
            (audit_dir / "latest-security-audit.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "generated_at": "2026-03-20T00:00:00Z",
                        "summary": {
                            "dashboard_operator": {
                                "status": "ok",
                                "report_path": str(report_path),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (audit_dir / "latest-dashboard-security-scan.json").write_text(
                report_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            os.environ["AI_SECURITY_AUDIT_DIR"] = str(audit_dir)
            import importlib

            dashboard_main = importlib.import_module("api.main")
            dashboard_main = importlib.reload(dashboard_main)

            with TestClient(dashboard_main.app) as client:
                response = client.get("/api/security/audit")
                assert_true(response.status_code == 200, "security audit route should succeed")
                payload = response.json()
                assert_true(payload.get("dashboard_operator", {}).get("status") == "ok", "dashboard operator scan should be exposed")
                assert_true(
                    payload.get("dashboard_operator", {}).get("summary", {}).get("audit_integrity_valid") is True,
                    "dashboard operator report should preserve integrity summary",
                )

        finally:
            server.shutdown()
            server.server_close()

    print("PASS: dashboard security scan automation regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
