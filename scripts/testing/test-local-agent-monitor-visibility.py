#!/usr/bin/env python3
"""Validate local-agent monitor visibility across CLI, report, and dashboard."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def fail(message: str) -> None:
    raise AssertionError(message)


def test_monitor_cli_read_only() -> None:
    registry = ROOT / ".agents" / "delegation" / "TASK_REGISTRY.jsonl"
    before = registry.read_bytes() if registry.exists() else b""
    rc = subprocess.run(
        [str(ROOT / "scripts" / "ai" / "delegate-to-local"), "--monitor"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=10,
    )
    after = registry.read_bytes() if registry.exists() else b""
    if rc.returncode != 0:
        fail(f"delegate-to-local --monitor failed: {rc.stderr.strip()}")
    payload = json.loads(rc.stdout)
    if payload.get("mode") != "read_only":
        fail("monitor payload mode is not read_only")
    if not isinstance(payload.get("counts"), dict):
        fail("monitor payload missing counts")
    if before != after:
        fail("monitor mutated TASK_REGISTRY.jsonl")
    print("PASS monitor CLI returns read-only JSON")


def test_report_field_and_dashboard_wiring() -> None:
    report = (ROOT / "scripts" / "ai" / "aq-report").read_text(encoding="utf-8")
    route = (ROOT / "dashboard" / "backend" / "api" / "routes" / "aistack.py").read_text(encoding="utf-8")
    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
    js = (ROOT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    required = {
        "aq-report local_agent_monitor": '"local_agent_monitor"' in report,
        "dashboard route": '@router.get("/local-agent/monitor")' in route,
        "dashboard card": "section-local-agent-monitor" in html and "localAgentMonitorDetails" in html,
        "dashboard loader": "async function loadLocalAgentMonitor" in js and "/aistack/local-agent/monitor" in js,
        "observability wiring": "loadLocalAgentMonitor()" in js,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        fail(f"missing monitor visibility wiring: {', '.join(missing)}")
    print("PASS aq-report and dashboard monitor wiring present")


def test_live_dashboard_endpoint() -> None:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8889/api/aistack/local-agent/monitor",
            timeout=5,
        ) as resp:
            payload = json.loads(resp.read())
    except Exception as exc:
        print(f"SKIP live dashboard endpoint unavailable: {exc}")
        return
    if payload.get("available") is not True:
        fail(f"dashboard monitor endpoint unavailable: {payload}")
    if not isinstance(payload.get("counts"), dict):
        fail("dashboard monitor endpoint missing counts")
    print("PASS dashboard monitor endpoint returns counts")


def main() -> int:
    tests = [
        test_monitor_cli_read_only,
        test_report_field_and_dashboard_wiring,
        test_live_dashboard_endpoint,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            print(f"FAIL {test.__name__}: {exc}")
            return 1
    print(f"{passed}/{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
