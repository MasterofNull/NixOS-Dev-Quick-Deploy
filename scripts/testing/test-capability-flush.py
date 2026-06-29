#!/usr/bin/env python3
"""Regression checks for the capability flush harness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ai" / "aq-capability-flush"


def fail(message: str) -> None:
    raise AssertionError(message)


def run_json(*args: str) -> dict:
    proc = subprocess.run(
        [str(SCRIPT), *args, "--json"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
        check=False,
    )
    if proc.returncode != 0:
        fail(f"{SCRIPT.name} {' '.join(args)} failed: {proc.stderr[-800:]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON output: {exc}: {proc.stdout[:800]}")


def test_static_wiring() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    required = [
        "aq-skill-auto",
        "aq-capability-intake",
        "delegate-to-local",
        "system-capability-catalog.json",
        "suggested-ai-repo-candidates.json",
        "curated-web-research-sources.json",
        "/api/aistack/local-agent/monitor",
        "/query",
        '"agent"',
    ]
    for needle in required:
        if needle not in source:
            fail(f"missing wiring marker: {needle}")
    if "127.0.0.1:8002" in source:
        fail("capability flush must use coordinator/RAG routes, not direct AIDB access")


def test_dry_run_payload() -> None:
    payload = run_json("--dry-run")
    if payload.get("status") != "ok":
        fail(f"unexpected dry-run status: {payload.get('status')}")
    selected = payload.get("selected_skills", {})
    if not selected.get("selected"):
        fail("no selected skills returned")
    catalog = payload.get("capability_catalog", {})
    if catalog.get("catalog_entries", 0) <= 0:
        fail("capability catalog was not loaded")
    if catalog.get("suggested_candidates", 0) <= 0:
        fail("suggested candidate catalog was not loaded")
    security = payload.get("security_gate_summary", {})
    if security.get("reports", 0) <= 0:
        fail("capability intake did not return reports")
    osint = payload.get("osint_workflows", {})
    if osint.get("workflow_count", 0) <= 0:
        fail("OSINT workflow catalog was not loaded")
    if "monitor" not in payload:
        fail("local-agent monitor summary missing")


def test_status_payload() -> None:
    payload = run_json("--status")
    monitor = payload.get("monitor", {})
    if "counts" not in monitor:
        fail("monitor counts missing")


def main() -> int:
    tests = [test_static_wiring, test_dry_run_payload, test_status_payload]
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures.append(f"FAIL {test.__name__}: {exc}")
            print(failures[-1])
    if failures:
        return 1
    print(f"PASS {len(tests)} capability flush checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
