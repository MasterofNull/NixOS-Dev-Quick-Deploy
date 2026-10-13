#!/usr/bin/env python3
"""Regression checks for DP-4 Pi-style multi-agent streaming canvas, agent tree, and guidance endpoints."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_event(run_id: str, event_type: str = "tool_call", **kwargs) -> str:
    ev = {
        "schema_version": "maeah.agent-run-event.v1",
        "event_id": f"ev-{run_id}-{event_type}-{kwargs.get('seq', 1)}",
        "event_type": event_type,
        "timestamp": kwargs.get("timestamp", "2026-10-13T12:00:00Z"),
        "source": "test",
        "run_id": run_id,
        "agent_id": kwargs.get("agent_id", run_id),
        "role": kwargs.get("role", "agent"),
        "model": kwargs.get("model", "local-qwen"),
        "status": kwargs.get("status", "running"),
        "tool_name": kwargs.get("tool_name"),
        "tokens": {"input": 40, "output": 80, "total": 120},
        "payload": kwargs.get("payload", {}),
    }
    return json.dumps(ev)


def main() -> int:
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory(prefix="test-pi-agent-streaming-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        events_file = tmp_path / "agent-run-events.jsonl"
        guidance_dir = tmp_path / "guidance"
        guidance_dir.mkdir(parents=True, exist_ok=True)

        os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = str(events_file)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        aistack_module = importlib.import_module("api.routes.aistack")
        dashboard_main = importlib.reload(dashboard_main)
        aistack_module = importlib.reload(aistack_module)

        with TestClient(dashboard_main.app) as client:

            # ── 1. agent-tree — empty fallback ────────────────────────────────
            try:
                r = client.get("/api/aistack/agent-tree")
                assert_true(r.status_code == 200, f"expected 200, got {r.status_code}")
                data = r.json()
                assert_true(data["available"] is True, "available should be true")
                assert_true(len(data["roots"]) >= 1, "roots should have fallback orchestrator")
                assert_true(data["roots"][0]["role"] == "orchestrator", "root role should be orchestrator")
                print("  PASS  DP-4: agent-tree returns fallback orchestrator when no events exist")
                passed += 1
            except Exception as e:
                print(f"  FAIL  DP-4: agent-tree empty fallback: {e}")
                failed += 1

            # ── 2. agent-tree — hierarchy with sub-agents ────────────────────
            try:
                records = [
                    # Root orchestrator
                    _make_event("run-root", "run_start", role="orchestrator", model="claude-fable-5", seq=1),
                    _make_event("run-root", "thought", role="orchestrator", payload={"thought": "Planning sub-agent tasks"}, seq=2),
                    # Spun-up Sub-agent 1: Triage
                    _make_event("run-sub-triage", "run_start", role="triage", model="local-qwen",
                                payload={"parent_run_id": "run-root", "name": "System 1 Triage"}, seq=1),
                    _make_event("run-sub-triage", "tool_call", tool_name="aq_triage_classify", seq=2),
                    # Spun-up Sub-agent 2: Implementer
                    _make_event("run-sub-impl", "run_start", role="implementer", model="local-qwen",
                                payload={"parent_run_id": "run-root", "name": "Isolated Implementer"}, seq=1),
                    _make_event("run-sub-impl", "run_end", status="done", seq=2),
                ]
                events_file.write_text("\n".join(records) + "\n", encoding="utf-8")

                r = client.get("/api/aistack/agent-tree")
                assert_true(r.status_code == 200, f"expected 200, got {r.status_code}")
                data = r.json()
                roots = data["roots"]
                assert_true(len(roots) == 1, f"expected 1 root, got {len(roots)}")
                root = roots[0]
                assert_true(root["run_id"] == "run-root", "root run_id should be run-root")
                assert_true(len(root["children"]) == 2, f"expected 2 children, got {len(root['children'])}")

                # Check children roles and statuses
                child_roles = {c["role"]: c for c in root["children"]}
                assert_true("triage" in child_roles, "triage child missing")
                assert_true(child_roles["triage"]["status"] == "tool_executing", "triage child should be tool_executing")
                assert_true(child_roles["triage"]["last_tool"] == "aq_triage_classify", "triage child last_tool mismatch")
                assert_true("implementer" in child_roles, "implementer child missing")
                assert_true(child_roles["implementer"]["status"] == "done", "implementer child should be done")

                print("  PASS  DP-4: agent-tree builds multi-agent hierarchy tree with sub-agents and statuses")
                passed += 1
            except Exception as e:
                print(f"  FAIL  DP-4: agent-tree hierarchy: {e}")
                failed += 1

            # ── 3. agent stream endpoint ─────────────────────────────────────
            try:
                r = client.get("/api/aistack/agent-runs/run-root/stream?tail=10&max_duration_seconds=5")
                assert_true(r.status_code == 200, f"expected 200, got {r.status_code}")
                assert_true("text/event-stream" in r.headers.get("content-type", ""), "content-type must be text/event-stream")

                body = r.text
                assert_true("event: lifecycle_delta" in body, "lifecycle_delta event missing in stream")
                assert_true("event: token_stream" in body, "token_stream event missing in stream")
                assert_true("event: stream_ready" in body, "stream_ready event missing in stream")
                print("  PASS  DP-4: agent-runs stream yields SSE events and stream_ready packet")
                passed += 1
            except Exception as e:
                print(f"  FAIL  DP-4: agent-runs stream: {e}")
                failed += 1

            # ── 4. operator guidance injection ───────────────────────────────
            try:
                payload = {
                    "prompt": "Prioritize verifying sub-agent worktrees before staging PR",
                    "operator_id": "operator-dan",
                    "action": "guidance",
                }
                r = client.post("/api/aistack/agent-runs/run-root/guidance", json=payload)
                assert_true(r.status_code == 200, f"expected 200, got {r.status_code}")
                res = r.json()
                assert_true(res["status"] == "injected", f"expected status injected, got {res.get('status')}")
                assert_true(res["guidance"] == payload["prompt"], "guidance prompt mismatch")
                assert_true(res["persisted"] is True, "guidance event should be persisted")

                # Verify GET guidance endpoint reads it back
                g_resp = client.get("/api/aistack/agent-runs/run-root/guidance")
                assert_true(g_resp.status_code == 200, f"expected 200, got {g_resp.status_code}")
                g_data = g_resp.json()
                assert_true(g_data.get("has_guidance") is True, "has_guidance should be true")
                assert_true(g_data["guidance"]["prompt"] == payload["prompt"], "retrieved guidance prompt mismatch")

                print("  PASS  DP-4: operator guidance injection persists human_control event and returns confirmation")
                passed += 1
            except Exception as e:
                print(f"  FAIL  DP-4: operator guidance injection: {e}")
                failed += 1

            # ── 5. human controls: step-approve, pause, resume ──────────────
            try:
                for action in ("step_approve", "pause", "resume"):
                    r = client.post(f"/api/aistack/agent-runs/run-root/control", json={"action": action, "operator_id": "test-op"})
                    assert_true(r.status_code == 200, f"expected 200 for action {action}, got {r.status_code}")
                    assert_true(r.json().get("action") == action, f"action mismatch for {action}")
                print("  PASS  DP-4: human control actions step_approve, pause, resume accepted and persisted")
                passed += 1
            except Exception as e:
                print(f"  FAIL  DP-4: human controls: {e}")
                failed += 1

    print(f"\n{passed}/{passed + failed} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
