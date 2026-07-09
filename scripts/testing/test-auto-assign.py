#!/usr/bin/env python3
"""Tests for agentic auto-assignment (scripts/ai/lib/auto_assign.py).

Run: python3 scripts/testing/test-auto-assign.py
"""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

import auto_assign  # noqa: E402


def test_role_normalization():
    assert auto_assign.normalize_role("implement") == "implementer"
    assert auto_assign.normalize_role("review") == "reviewer"
    assert auto_assign.normalize_role("REVIEWER") == "reviewer"
    assert auto_assign.normalize_role("auto") is None
    assert auto_assign.normalize_role(None) is None
    assert auto_assign.normalize_role("bogus-role") is None
    print("PASS role normalization (incl. legacy 'implement' alias)")


def test_role_inference():
    assert auto_assign.resolve_role(None, "Review this PRD and give a verdict") == "reviewer"
    assert auto_assign.resolve_role("auto", "Design the architecture for the event bus") == "architect"
    assert auto_assign.resolve_role(None, "Fix the failing import in dispatch.py") == "implementer"
    assert auto_assign.resolve_role(None, "hello") == "implementer"  # fallback
    # explicit canonical role always wins over prompt signals
    assert auto_assign.resolve_role("reviewer", "implement the fix") == "reviewer"
    # inference never yields orchestrator (sub-agent rule)
    assert auto_assign.resolve_role(None, "orchestrate and delegate all the slices") != "orchestrator"
    print("PASS role inference + sub-agent non-orchestrator rule")


def test_band_inference():
    assert auto_assign.infer_band("aq-loop", "anything") == "background"
    assert auto_assign.infer_band("aq-chat", "anything") == "interactive"
    assert auto_assign.infer_band("collab-round", "anything") == "consensus"
    assert auto_assign.infer_band(None, "nightly batch cleanup of the backlog") == "background"
    assert auto_assign.infer_band(None, "cast your consensus vote on this plan") == "consensus"
    assert auto_assign.infer_band(None, "summarize this file") == "consensus"  # safe default
    print("PASS band inference")


def test_task_class_inference():
    assert auto_assign.infer_task_class("classify these log lines by severity") == "classification"
    assert auto_assign.infer_task_class("repair json output from the model") == "json_repair"
    assert auto_assign.infer_task_class("cast a consensus vote") == "consensus_vote"
    assert auto_assign.infer_task_class("triage the failing test stack trace") == "test_error_triage"
    assert auto_assign.infer_task_class("write a poem") is None
    print("PASS task_class inference")


def test_kill_switch():
    os.environ["AUTO_ASSIGN"] = "0"
    assert auto_assign.resolve_role(None, "review this") == "implementer"
    assert auto_assign.infer_task_class("classify this") is None
    assert auto_assign.skill_hints("async python", REPO) == []
    os.environ.pop("AUTO_ASSIGN")
    print("PASS kill switch")


def test_skill_hints_live():
    hints = auto_assign.skill_hints("fix async python handler blocking the event loop", REPO)
    assert "python-async" in hints, hints
    block = auto_assign.skill_hint_block("fix async python handler blocking the event loop", REPO)
    assert "Auto-suggested skills" in block and "python-async" in block
    print(f"PASS live skill hints: {hints}")


def test_skill_hints_fail_open():
    hints = auto_assign.skill_hints("whatever", Path("/nonexistent"))
    assert hints == []
    print("PASS skill hints fail-open")


if __name__ == "__main__":
    test_role_normalization()
    test_role_inference()
    test_band_inference()
    test_task_class_inference()
    test_kill_switch()
    test_skill_hints_fail_open()
    test_skill_hints_live()
    print("ALL PASS")
