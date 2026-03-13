#!/usr/bin/env python3
"""Targeted checks for workflow reviewer-gate reporting."""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-report"
SPEC = importlib.util.spec_from_loader("aq_report", SourceFileLoader("aq_report", str(MODULE_PATH)))
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-report module")
MODULE = importlib.util.module_from_spec(SPEC)
os.environ.setdefault("AI_STRICT_ENV", "false")
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    original_path = MODULE.WORKFLOW_SESSIONS_PATH
    tmp_path = ROOT / ".tmp-workflow-review-gate.json"
    now = datetime.now(tz=timezone.utc)
    now_epoch = int(now.timestamp())
    try:
        payload = {
            "review-session": {
                "session_id": "review-session",
                "objective": "review smoke",
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "intent_contract": {
                    "user_intent": "review smoke",
                    "definition_of_done": "gate stored",
                    "depth_expectation": "standard",
                    "spirit_constraints": ["stay bounded"],
                    "no_early_exit_without": ["review state"],
                },
                "reviewer_gate": {
                    "required": True,
                    "status": "accepted",
                    "history": [{"ts": now_epoch, "passed": True, "score": 1.0}],
                    "last_review": {"ts": now_epoch, "passed": True, "score": 1.0, "reviewer": "codex"},
                },
                "blueprint_id": "repo-refactor-guarded",
                "orchestration": {
                    "requesting_agent": "continue",
                    "requester_role": "orchestrator",
                    "delegate_via_coordinator_only": True,
                },
            },
            "pending-session": {
                "session_id": "pending-session",
                "objective": "pending smoke",
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "intent_contract": {
                    "user_intent": "pending smoke",
                    "definition_of_done": "pending gate",
                    "depth_expectation": "deep",
                    "spirit_constraints": ["stay explicit"],
                    "no_early_exit_without": ["review state"],
                },
                "reviewer_gate": {
                    "required": True,
                    "status": "pending_review",
                    "history": [],
                },
                "blueprint_id": "continue-editor-rescue",
                "orchestration": {
                    "requesting_agent": "qwen",
                    "requester_role": "sub-agent",
                    "delegate_via_coordinator_only": True,
                },
            },
            "rejected-session": {
                "session_id": "rejected-session",
                "objective": "rejected smoke",
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "intent_contract": {
                    "user_intent": "rejected smoke",
                    "definition_of_done": "rejected gate",
                    "depth_expectation": "minimum",
                    "spirit_constraints": ["stay bounded"],
                    "no_early_exit_without": ["review state"],
                },
                "reviewer_gate": {
                    "required": True,
                    "status": "rejected",
                    "history": [{"ts": now_epoch, "passed": False, "score": 0.2}],
                    "last_review": {"ts": now_epoch, "passed": False, "score": 0.2, "reviewer": "codex"},
                },
                "blueprint_id": "continue-editor-rescue",
                "orchestration": {
                    "requesting_agent": "continue",
                    "requester_role": "orchestrator",
                    "delegate_via_coordinator_only": True,
                },
            },
        }
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        MODULE.WORKFLOW_SESSIONS_PATH = tmp_path
        summary = MODULE.read_workflow_sessions(now - timedelta(days=1))
        assert_true(summary.get("reviewer_gate_required_runs") == 3, "expected three reviewer-gated runs")
        assert_true(summary.get("sessions_with_reviews") == 2, "expected two reviewed sessions")
        assert_true(summary.get("accepted_reviews") == 1, "expected one accepted review")
        assert_true(summary.get("rejected_reviews") == 1, "expected one rejected review")
        assert_true(summary.get("pending_reviews") == 1, "expected one pending review")
        assert_true(any(role == "orchestrator" and count == 2 for role, count in (summary.get("top_requester_roles") or [])), "expected requester role summary")
        assert_true(any(role == "orchestrator" and count == 1 for role, count in (summary.get("accepted_by_requester_role") or [])), "expected accepted role summary")
        assert_true(any(reviewer == "codex" and count == 2 for reviewer, count in (summary.get("top_reviewers") or [])), "expected reviewer summary")
        assert_true(any(bp == "repo-refactor-guarded" and count == 1 for bp, count in (summary.get("accepted_blueprints") or [])), "expected accepted blueprint summary")
        assert_true(any(bp == "continue-editor-rescue" and count == 1 for bp, count in (summary.get("rejected_blueprints") or [])), "expected rejected blueprint summary")
    finally:
        MODULE.WORKFLOW_SESSIONS_PATH = original_path
        if tmp_path.exists():
            tmp_path.unlink()

    print("PASS: aq-report summarizes reviewer-gate workflow state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
