#!/usr/bin/env python3
"""Regression tests for aq-inference-bench."""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CMD = ROOT / "scripts" / "ai" / "aq-inference-bench"
BENCH = ROOT / "config" / "aq-inference-benchmarks.json"
SCHEMA = ROOT / "config" / "schemas" / "aq-inference-benchmarks.schema.json"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CMD), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def load_stdout(proc: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(proc.stdout)


def fixture_payload(base_url: str) -> dict:
    return {
        "$schema": "./schemas/aq-inference-benchmarks.schema.json",
        "version": "test",
        "owner": "qa-automation",
        "policy": {
            "source_of_truth": "config/aq-inference-benchmarks.json",
            "default_mode": "dry-run",
            "localhost_only": True,
            "external_runtimes_enabled": False,
            "activation_gate": "capability-intake"
        },
        "backends": [
            {
                "id": "fake-local",
                "runtime": "fixture",
                "status": "enabled",
                "base_url": base_url,
                "chat_path": "/v1/chat/completions",
                "health_path": "/health",
                "metrics_path": "/metrics",
                "service": "fixture.service",
                "authority": ["localhost-fixture"],
                "observability": [
                    "ttft_ms",
                    "tokens_per_sec",
                    "context_tokens",
                    "json_valid_rate",
                    "thermal_tier",
                    "memory_pressure"
                ]
            }
        ],
        "cases": [
            {
                "id": "exact-short-answer",
                "prompt": "Reply with exactly: INFERENCE_BENCH_OK",
                "max_tokens": 12,
                "validation": "exact:INFERENCE_BENCH_OK"
            },
            {
                "id": "strict-json",
                "prompt": "Return valid JSON only with keys \"decision\" and \"reason\". Use decision=\"hold\".",
                "max_tokens": 80,
                "validation": "json_object_keys:decision,reason"
            }
        ]
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{\"status\":\"ok\"}")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        content = "{\"decision\":\"hold\",\"reason\":\"fixture\"}" if "valid JSON" in prompt else "INFERENCE_BENCH_OK"
        body = {
            "choices": [{"message": {"content": content}}],
            "usage": {"completion_tokens": max(1, len(content.split()))}
        }
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def write_temp(payload: dict) -> str:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
    with handle:
        json.dump(payload, handle)
    return handle.name


def test_validate_and_list() -> None:
    assert BENCH.exists()
    assert SCHEMA.exists()
    validate = load_stdout(run("--json", "validate"))
    assert validate["status"] == "pass"
    assert validate["backend_count"] >= 1
    listed = load_stdout(run("--json", "list"))
    assert "llama-cpp-local" in {backend["id"] for backend in listed["backends"]}


def test_dry_run_never_executes_network() -> None:
    dry_run = load_stdout(run("--json", "run"))
    assert dry_run["status"] == "pass"
    assert dry_run["mode"] == "dry-run"
    assert all(result["status"] == "dry-run" for result in dry_run["results"])


def test_non_localhost_backend_rejected() -> None:
    payload = fixture_payload("https://example.com")
    path = write_temp(payload)
    proc = run("--bench-file", path, "--json", "validate", check=False)
    output = load_stdout(proc)
    assert proc.returncode == 1
    assert output["status"] == "fail"
    assert any("base_url must be http localhost" in error for error in output["errors"])


def test_execute_against_fake_localhost_endpoint() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        path = write_temp(fixture_payload(f"http://127.0.0.1:{port}"))
        output = load_stdout(
            run("--bench-file", path, "--json", "run", "--execute", "--backend", "fake-local", "--timeout-seconds", "5")
        )
        assert output["status"] == "pass"
        result = output["results"][0]
        assert result["status"] == "pass"
        assert result["metrics"]["json_valid_rate"] == 1.0
        assert result["metrics"]["tokens_per_sec"] > 0
    finally:
        server.shutdown()
        thread.join(timeout=5)


def main() -> int:
    test_validate_and_list()
    test_dry_run_never_executes_network()
    test_non_localhost_backend_rejected()
    test_execute_against_fake_localhost_endpoint()
    print("PASS: aq-inference-bench checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
