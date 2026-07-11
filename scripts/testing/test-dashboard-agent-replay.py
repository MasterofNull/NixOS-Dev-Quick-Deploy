#!/usr/bin/env python3
"""Regression checks for Phase 93.6-93.8 and 93.13 dashboard agent-run observability routes."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_run_event(run_id: str, event_type: str = "tool_call", **kwargs) -> str:
    ev = {
        "schema_version": "maeah.agent-run-event.v1",
        "event_id": f"ev-{run_id}-{event_type}",
        "event_type": event_type,
        "timestamp": "2026-06-01T10:00:00Z",
        "source": "test",
        "run_id": run_id,
        "experiment_id": kwargs.get("experiment_id"),
        "agent_id": kwargs.get("agent_id", "local"),
        "spec": {"variant": kwargs.get("variant", "markdown"), "canonical_path": None, "derived_path": None, "source_hash": None, "generator": None},
        "tokens": {"input": 50, "output": 100, "accepted_artifact": 90, "total": 200, "useful_ratio": 0.8},
        "status": kwargs.get("status", "succeeded"),
        "tool_name": kwargs.get("tool_name"),
        "payload": kwargs.get("payload", {}),
    }
    return json.dumps(ev)


def main() -> int:
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory(prefix="test-dashboard-agent-replay-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        events_file = tmp_path / "agent-run-events.jsonl"
        race_file = tmp_path / "race-runs.jsonl"
        focused_ci_file = tmp_path / "latest-focused-ci.json"
        aq_report_file = tmp_path / "latest-aq-report.json"

        os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = str(events_file)
        os.environ["AQ_RACE_RUNS_PATH"] = str(race_file)
        os.environ["AQ_FOCUSED_CI_JSON_PATH"] = str(focused_ci_file)
        os.environ["AQ_REPORT_LATEST_JSON"] = str(aq_report_file)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        aistack_module = importlib.import_module("api.routes.aistack")
        dashboard_main = importlib.reload(dashboard_main)
        aistack_module = importlib.reload(aistack_module)

        with TestClient(dashboard_main.app) as client:

            # ── 93.6: single-agent replay — no events file ────────────────────
            name = "93.6: replay route returns no_data when events file absent"
            try:
                resp = client.get("/api/aistack/agent-runs/run-abc123")
                assert_true(resp.status_code == 200, f"status={resp.status_code}")
                body = resp.json()
                assert_true(body.get("available") is False, "available=False when no events")
                assert_true(body.get("run_id") == "run-abc123", "run_id preserved in response")
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

            # ── 93.6: single-agent replay — with events ───────────────────────
            name = "93.6: replay route returns timeline when events exist"
            try:
                events_file.write_text(
                    _make_run_event("run-xyz", "tool_call", tool_name="rg") + "\n" +
                    _make_run_event("run-xyz", "artifact", payload={"path": "/tmp/out.md"}) + "\n"
                )
                aistack_module._AGENT_RUN_EVENTS_PATH = events_file
                resp = client.get("/api/aistack/agent-runs/run-xyz")
                assert_true(resp.status_code == 200, f"status={resp.status_code}")
                body = resp.json()
                assert_true(body.get("available") is True, "available=True with events")
                assert_true(body.get("event_count") == 2, f"event_count=2, got {body.get('event_count')}")
                assert_true("timeline" in body, "timeline key present")
                assert_true("tool_heatmap" in body, "tool_heatmap key present")
                assert_true("summary" in body, "summary key present")
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

            # ── 93.7: list runs — no events ───────────────────────────────────
            name = "93.7: list runs returns empty when events file absent"
            try:
                events_file.unlink(missing_ok=True)
                aistack_module._AGENT_RUN_EVENTS_PATH = events_file
                resp = client.get("/api/aistack/agent-runs")
                assert_true(resp.status_code == 200, f"status={resp.status_code}")
                body = resp.json()
                assert_true("runs" in body, "runs key present")
                assert_true(body.get("count", -1) == 0, f"count=0 with no file, got {body.get('count')}")
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

            # ── 93.7: list runs — with multiple runs ──────────────────────────
            name = "93.7: list runs returns summaries for multiple runs"
            try:
                events_file.write_text(
                    _make_run_event("run-1", "run_start", agent_id="local", variant="markdown") + "\n" +
                    _make_run_event("run-2", "run_start", agent_id="gemini", variant="html") + "\n"
                )
                aistack_module._AGENT_RUN_EVENTS_PATH = events_file
                resp = client.get("/api/aistack/agent-runs")
                assert_true(resp.status_code == 200, f"status={resp.status_code}")
                body = resp.json()
                assert_true(body.get("count", 0) >= 2, f"at least 2 runs listed, got {body.get('count')}")
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

            # ── 93.8: human control — invalid action → 422 ───────────────────
            name = "93.8: control endpoint rejects invalid action with 422"
            try:
                resp = client.post(
                    "/api/aistack/agent-runs/run-xyz/control",
                    json={"action": "destroy_everything", "reason": "test"},
                )
                assert_true(resp.status_code == 422, f"expected 422, got {resp.status_code}")
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

            # ── 93.8: human control — valid action → 200 + event written ─────
            name = "93.8: control endpoint accepts valid action and persists event"
            try:
                events_file.unlink(missing_ok=True)
                aistack_module._AGENT_RUN_EVENTS_PATH = events_file
                resp = client.post(
                    "/api/aistack/agent-runs/run-xyz/control",
                    json={"action": "approve", "reason": "looks good", "operator_id": "hyperd"},
                )
                assert_true(resp.status_code == 200, f"expected 200, got {resp.status_code}")
                body = resp.json()
                assert_true(body.get("action") == "approve", "action echoed in response")
                assert_true("event_id" in body, "event_id present in response")
                assert_true(body.get("persisted") is True, "event should be persisted to JSONL")
                # Verify the event was actually written
                written = json.loads(events_file.read_text().strip())
                assert_true(written.get("event_type") == "human_control", "event_type=human_control")
                assert_true(written.get("schema_version") == "maeah.agent-run-event.v1", "schema_version correct")
                assert_true(written.get("run_id") == "run-xyz", "run_id correct in persisted event")
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

            # ── 93.13: effectiveness scorecard — no artifact ──────────────────
            name = "93.13: scorecard endpoint returns no_data when artifact absent"
            try:
                resp = client.get("/api/aistack/effectiveness/scorecard")
                assert_true(resp.status_code == 200, f"status={resp.status_code}")
                body = resp.json()
                assert_true(body.get("available") is False, "available=False when artifact absent")
                assert_true(body.get("status") == "no_data", f"status=no_data, got {body.get('status')}")
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

            # ── 93.13: effectiveness scorecard — with artifact ────────────────
            name = "93.13: scorecard endpoint reads artifact and returns scorecard"
            try:
                report = {
                    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "effectiveness_scorecard": {
                        "schema_version": "aq.effectiveness-scorecard.v1",
                        "overall_status": "pass",
                        "gate_outcome": "PASS",
                        "evidence_condition": "VALID",
                        "automation_allowed": True,
                        "outcome_correctness": {"status": "pass", "eval_pass_rate": 0.92},
                        "blocking_reasons": [],
                        "provenance": {"run_id": "qa-fixture", "start_sequence": 7, "sha256": "a" * 64, "age_seconds": 1.0, "hash_verified": True},
                        "operator_action": "rerun evidence",
                    },
                }
                aq_report_file.write_text(json.dumps(report))
                resp = client.get("/api/aistack/effectiveness/scorecard")
                assert_true(resp.status_code == 200, f"status={resp.status_code}")
                body = resp.json()
                assert_true(body.get("available") is True, "available=True with artifact")
                assert_true(body.get("status") == "pass", f"status=pass, got {body.get('status')}")
                assert_true(body.get("stale") is False, "report should not be stale")
                sc = body.get("effectiveness_scorecard") or {}
                assert_true(sc.get("overall_status") == "pass", "scorecard overall_status preserved")
                assert_true(body.get("provenance") == sc.get("provenance"), "API projects canonical provenance unchanged")
                assert_true(body.get("blocking_reasons") == sc.get("blocking_reasons"), "API projects canonical reasons unchanged")
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

    total = passed + failed
    if failed:
        print(f"\n{failed}/{total} tests FAILED")
        return 1
    print(f"\n{total}/{total} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
