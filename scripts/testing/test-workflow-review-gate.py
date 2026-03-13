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
                },
                "blueprint_id": "repo-refactor-guarded",
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
            },
        }
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        MODULE.WORKFLOW_SESSIONS_PATH = tmp_path
        summary = MODULE.read_workflow_sessions(now - timedelta(days=1))
        assert_true(summary.get("reviewer_gate_required_runs") == 2, "expected two reviewer-gated runs")
        assert_true(summary.get("sessions_with_reviews") == 1, "expected one reviewed session")
        assert_true(summary.get("accepted_reviews") == 1, "expected one accepted review")
        assert_true(summary.get("pending_reviews") == 1, "expected one pending review")
    finally:
        MODULE.WORKFLOW_SESSIONS_PATH = original_path
        if tmp_path.exists():
            tmp_path.unlink()

    print("PASS: aq-report summarizes reviewer-gate workflow state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
