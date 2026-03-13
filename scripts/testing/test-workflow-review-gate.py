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
                    "last_review": {
                        "ts": now_epoch,
                        "passed": True,
                        "score": 1.0,
                        "reviewer": "codex",
                        "review_type": "patch_review",
                        "artifact_kind": "patch",
                        "task_class": "repo_refactor",
                        "reviewed_agent": "qwen",
                        "reviewed_profile": "remote-coding",
                    },
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
                    "last_review": {
                        "ts": now_epoch,
                        "passed": False,
                        "score": 0.0,
                        "reviewer": "codex",
                        "review_type": "plan_review",
                        "artifact_kind": "plan",
                        "task_class": "remote_reasoning",
                        "reviewed_agent": "claude",
                        "reviewed_profile": "remote-reasoning",
                    },
                },
                "blueprint_id": "remote-reasoning-escalation",
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
                    "last_review": {
                        "ts": now_epoch,
                        "passed": False,
                        "score": 0.2,
                        "reviewer": "codex",
                        "review_type": "patch_review",
                        "artifact_kind": "patch",
                        "task_class": "editor_rescue",
                        "reviewed_agent": "qwen",
                        "reviewed_profile": "continue-local",
                    },
                },
                "blueprint_id": "continue-editor-rescue",
                "orchestration": {
                    "requesting_agent": "continue",
                    "requester_role": "orchestrator",
                    "delegate_via_coordinator_only": True,
                },
            },
            "deploy-session": {
                "session_id": "deploy-session",
                "objective": "deploy smoke",
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "intent_contract": {
                    "user_intent": "deploy smoke",
                    "definition_of_done": "artifact review stored",
                    "depth_expectation": "standard",
                    "spirit_constraints": ["stay bounded"],
                    "no_early_exit_without": ["review state"],
                },
                "reviewer_gate": {
                    "required": True,
                    "status": "accepted",
                    "history": [{"ts": now_epoch, "passed": True, "score": 1.0}],
                    "last_review": {
                        "ts": now_epoch,
                        "passed": True,
                        "score": 1.0,
                        "reviewer": "codex",
                        "review_type": "artifact_review",
                        "artifact_kind": "runbook",
                        "task_class": "deploy_safe_ops",
                        "reviewed_agent": "gemini",
                        "reviewed_profile": "remote-free",
                    },
                },
                "blueprint_id": "deploy-rollback-safe-ops",
                "orchestration": {
                    "requesting_agent": "continue",
                    "requester_role": "orchestrator",
                    "delegate_via_coordinator_only": True,
                },
            },
            "bugfix-session": {
                "session_id": "bugfix-session",
                "objective": "bugfix smoke",
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "intent_contract": {
                    "user_intent": "bugfix smoke",
                    "definition_of_done": "acceptance review stored",
                    "depth_expectation": "standard",
                    "spirit_constraints": ["stay bounded"],
                    "no_early_exit_without": ["review state"],
                },
                "reviewer_gate": {
                    "required": True,
                    "status": "accepted",
                    "history": [{"ts": now_epoch, "passed": True, "score": 1.0}],
                    "last_review": {
                        "ts": now_epoch,
                        "passed": True,
                        "score": 1.0,
                        "reviewer": "codex",
                        "review_type": "acceptance",
                        "artifact_kind": "response",
                        "task_class": "coding_bugfix",
                        "reviewed_agent": "qwen",
                        "reviewed_profile": "remote-coding",
                    },
                },
                "blueprint_id": "coding-bugfix-safe",
                "orchestration": {
                    "requesting_agent": "continue",
                    "requester_role": "orchestrator",
                    "delegate_via_coordinator_only": True,
                },
            },
            "hardening-session": {
                "session_id": "hardening-session",
                "objective": "hardening smoke",
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "intent_contract": {
                    "user_intent": "hardening smoke",
                    "definition_of_done": "hardening review stored",
                    "depth_expectation": "standard",
                    "spirit_constraints": ["stay bounded"],
                    "no_early_exit_without": ["review state"],
                },
                "reviewer_gate": {
                    "required": True,
                    "status": "accepted",
                    "history": [{"ts": now_epoch, "passed": True, "score": 1.0}],
                    "last_review": {
                        "ts": now_epoch,
                        "passed": True,
                        "score": 1.0,
                        "reviewer": "codex",
                        "review_type": "artifact_review",
                        "artifact_kind": "runbook",
                        "task_class": "nixos_service_hardening",
                        "reviewed_agent": "claude",
                        "reviewed_profile": "remote-reasoning",
                    },
                },
                "blueprint_id": "nixos-service-hardening",
                "orchestration": {
                    "requesting_agent": "continue",
                    "requester_role": "orchestrator",
                    "delegate_via_coordinator_only": True,
                },
            },
            "prsi-session": {
                "session_id": "prsi-session",
                "objective": "prsi smoke",
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "intent_contract": {
                    "user_intent": "prsi smoke",
                    "definition_of_done": "cycle review stored",
                    "depth_expectation": "deep",
                    "spirit_constraints": ["stay bounded"],
                    "no_early_exit_without": ["review state"],
                },
                "reviewer_gate": {
                    "required": True,
                    "status": "accepted",
                    "history": [{"ts": now_epoch, "passed": True, "score": 1.0}],
                    "last_review": {
                        "ts": now_epoch,
                        "passed": True,
                        "score": 1.0,
                        "reviewer": "codex",
                        "review_type": "artifact_review",
                        "artifact_kind": "cycle_report",
                        "task_class": "self_improvement",
                        "reviewed_agent": "claude",
                        "reviewed_profile": "remote-reasoning",
                    },
                },
                "blueprint_id": "prsi-pessimistic-recursive-improvement",
                "orchestration": {
                    "requesting_agent": "continue",
                    "requester_role": "orchestrator",
                    "delegate_via_coordinator_only": True,
                },
            },
            "research-session": {
                "session_id": "research-session",
                "objective": "research smoke",
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "intent_contract": {
                    "user_intent": "research smoke",
                    "definition_of_done": "research review stored",
                    "depth_expectation": "standard",
                    "spirit_constraints": ["stay bounded"],
                    "no_early_exit_without": ["review state"],
                },
                "reviewer_gate": {
                    "required": True,
                    "status": "accepted",
                    "history": [{"ts": now_epoch, "passed": True, "score": 1.0}],
                    "last_review": {
                        "ts": now_epoch,
                        "passed": True,
                        "score": 1.0,
                        "reviewer": "codex",
                        "review_type": "artifact_review",
                        "artifact_kind": "research_brief",
                        "task_class": "retrieval_research",
                        "reviewed_agent": "gemini",
                        "reviewed_profile": "remote-free",
                    },
                },
                "blueprint_id": "bounded-research-review",
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
        assert_true(summary.get("reviewer_gate_required_runs") == 8, "expected eight reviewer-gated runs")
        assert_true(summary.get("sessions_with_reviews") == 7, "expected seven reviewed sessions")
        assert_true(summary.get("accepted_reviews") == 6, "expected six accepted reviews")
        assert_true(summary.get("rejected_reviews") == 1, "expected one rejected review")
        assert_true(summary.get("pending_reviews") == 1, "expected one pending review")
        assert_true(any(role == "orchestrator" and count == 7 for role, count in (summary.get("top_requester_roles") or [])), "expected requester role summary")
        assert_true(any(role == "orchestrator" and count == 6 for role, count in (summary.get("accepted_by_requester_role") or [])), "expected accepted role summary")
        assert_true(any(reviewer == "codex" and count == 8 for reviewer, count in (summary.get("top_reviewers") or [])), "expected reviewer summary")
        assert_true(any(review_type == "artifact_review" and count == 4 for review_type, count in (summary.get("top_review_types") or [])), "expected review type summary")
        assert_true(len(summary.get("accepted_blueprints") or []) >= 5, "expected accepted blueprint coverage summary")
        assert_true(any(bp == "continue-editor-rescue" and count == 1 for bp, count in (summary.get("rejected_blueprints") or [])), "expected rejected blueprint summary")
        assert_true(summary.get("accepted_patch_reviews") == 1, "expected one accepted patch review")
        assert_true(summary.get("rejected_patch_reviews") == 1, "expected one rejected patch review")
        assert_true(any(agent == "qwen" and count == 2 for agent, count in (summary.get("patch_reviews_by_reviewed_agent") or [])), "expected patch-reviewed agent summary")
        assert_true(any(task_class == "repo_refactor" and count == 1 for task_class, count in (summary.get("accepted_task_classes") or [])), "expected accepted task class summary")
        assert_true(any(task_class == "deploy_safe_ops" and count == 1 for task_class, count in (summary.get("accepted_task_classes") or [])), "expected accepted deploy task class summary")
        assert_true(any(task_class == "coding_bugfix" and count == 1 for task_class, count in (summary.get("accepted_task_classes") or [])), "expected accepted bugfix task class summary")
        assert_true(any(task_class == "nixos_service_hardening" and count == 1 for task_class, count in (summary.get("accepted_task_classes") or [])), "expected accepted hardening task class summary")
        assert_true(any(task_class == "retrieval_research" and count == 1 for task_class, count in (summary.get("accepted_task_classes") or [])), "expected accepted research task class summary")
        assert_true(any(task_class == "editor_rescue" and count == 1 for task_class, count in (summary.get("rejected_task_classes") or [])), "expected rejected task class summary")
        assert_true(any(profile == "remote-coding" and count == 2 for profile, count in (summary.get("accepted_by_reviewed_profile") or [])), "expected accepted reviewed-profile summary")
        assert_true(any(profile == "remote-free" and count == 2 for profile, count in (summary.get("accepted_by_reviewed_profile") or [])), "expected accepted remote-free reviewed-profile summary")
        assert_true(any(profile == "remote-reasoning" and count == 2 for profile, count in (summary.get("accepted_by_reviewed_profile") or [])), "expected accepted remote-reasoning reviewed-profile summary")
        assert_true(any(profile == "continue-local" and count == 1 for profile, count in (summary.get("rejected_by_reviewed_profile") or [])), "expected rejected reviewed-profile summary")
    finally:
        MODULE.WORKFLOW_SESSIONS_PATH = original_path
        if tmp_path.exists():
            tmp_path.unlink()

    print("PASS: aq-report summarizes reviewer-gate workflow state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
