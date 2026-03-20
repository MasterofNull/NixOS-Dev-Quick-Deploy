#!/usr/bin/env python3
"""Targeted checks for workflow orchestration role defaults."""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))


class _DummyLogger:
    def bind(self, **kwargs):
        return self

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(get_logger=lambda *args, **kwargs: _DummyLogger())
if "mcp" not in sys.modules:
    mcp_module = types.ModuleType("mcp")
    mcp_types_module = types.ModuleType("mcp.types")
    class _DummyMcpType:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    mcp_types_module.TextContent = _DummyMcpType
    mcp_types_module.Tool = _DummyMcpType
    mcp_module.types = mcp_types_module
    sys.modules["mcp"] = mcp_module
    sys.modules["mcp.types"] = mcp_types_module

from ai_coordinator import coerce_orchestration_context  # noqa: E402
from http_server import (  # noqa: E402
    _apply_arbiter_update,
    _apply_consensus_update,
    _build_orchestration_team,
    _build_workflow_run_session,
    _default_agent_evaluations_registry,
    _load_agent_evaluations_registry_sync,
    _record_agent_consensus_event,
    _record_agent_review_event,
    _record_agent_runtime_event,
    _save_agent_evaluations_registry,
    _seed_agent_evaluation,
)

BLUEPRINTS_PATH = ROOT / "config" / "workflow-blueprints.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    default_ctx = coerce_orchestration_context({})
    assert_true(default_ctx["requester_role"] == "orchestrator", "default requester should be orchestrator")
    assert_true(default_ctx["top_level_orchestrator"] is True, "default requester should be top-level orchestrator")
    assert_true(default_ctx["subagents_may_spawn_subagents"] is False, "nested sub-agent spawning must stay disabled")
    assert_true(default_ctx["delegate_via_coordinator_only"] is True, "delegation must flow back through coordinator")

    sub_ctx = coerce_orchestration_context({"requesting_agent": "qwen", "requester_role": "sub-agent"})
    assert_true(sub_ctx["requested_by"] == "qwen", "requesting agent should be preserved")
    assert_true(sub_ctx["requester_role"] == "sub-agent", "sub-agent role should be preserved")
    assert_true(sub_ctx["top_level_orchestrator"] is False, "sub-agent must not be treated as top-level orchestrator")
    assert_true(sub_ctx["coordinator_delegate_path"] == "/control/ai-coordinator/delegate", "handoff path should be explicit")

    alias_ctx = coerce_orchestration_context({"agent": "continue", "role": "orchestrator"})
    assert_true(alias_ctx["requested_by"] == "continue", "legacy agent alias should normalize into requesting_agent")
    assert_true(alias_ctx["requester_role"] == "orchestrator", "legacy role alias should normalize into requester_role")

    payload = json.loads(BLUEPRINTS_PATH.read_text(encoding="utf-8"))
    blueprints = {item.get("id"): item for item in (payload.get("blueprints") or []) if isinstance(item, dict)}
    reasoning_policy = (blueprints.get("remote-reasoning-escalation") or {}).get("orchestration_policy") or {}
    assert_true(reasoning_policy.get("primary_lane") == "reasoning", "remote reasoning blueprint should route into reasoning lane")
    assert_true(reasoning_policy.get("selection_strategy") == "escalate-on-complexity", "remote reasoning blueprint should expose explicit escalation strategy")
    assert_true(reasoning_policy.get("consensus_mode") == "arbiter-review", "remote reasoning blueprint should use arbiter review")
    hardening_policy = (blueprints.get("nixos-service-hardening") or {}).get("orchestration_policy") or {}
    assert_true(hardening_policy.get("primary_lane") == "hardening", "hardening blueprint should expose hardening lane")
    assert_true(hardening_policy.get("consensus_mode") == "reviewer-gate", "hardening blueprint should stay reviewer-gated")

    arbiter_session = _build_workflow_run_session(
        query="Validate orchestrated consensus behavior",
        data={"blueprint_id": "remote-reasoning-escalation"},
        selected_blueprint=blueprints.get("remote-reasoning-escalation"),
        orchestration=default_ctx,
        lesson_refs=[],
    )
    consensus = arbiter_session.get("consensus") or {}
    candidates = consensus.get("candidates") or []
    assert_true(consensus.get("status") == "pending", "new sessions should seed pending consensus state")
    assert_true(len(candidates) >= 2, "session consensus should seed multiple candidates")
    assert_true(bool(consensus.get("selected_candidate_id")), "session consensus should select an initial candidate")
    team = arbiter_session.get("team") or {}
    assert_true(team.get("formation_mode") == "dynamic-role-assignment", "arbiter session should seed dynamic team assignment")
    assert_true("primary" in (team.get("active_slots") or []), "team should include a primary slot")
    assert_true("reviewer" in (team.get("active_slots") or []), "team should include a reviewer slot")
    assert_true("escalation" in (team.get("active_slots") or []), "arbiter-review team should include the escalation slot")
    arbiter_state = consensus.get("arbiter") or {}
    assert_true(arbiter_state.get("required") is True, "arbiter-review sessions should require arbiter input")
    assert_true(arbiter_state.get("status") == "pending", "arbiter-review sessions should start pending arbiter state")

    arbiter_candidate_id = next((str(item.get("candidate_id") or "") for item in candidates if item.get("candidate_id") == "escalation"), "")
    if not arbiter_candidate_id:
        arbiter_candidate_id = str(consensus.get("selected_candidate_id") or "")
    arbiter_updated = _apply_arbiter_update(
        arbiter_session,
        selected_candidate_id=arbiter_candidate_id,
        arbiter="codex",
        verdict="prefer",
        rationale="remote reasoning is warranted for this workflow",
        summary="arbiter selected the escalation lane",
        supporting_decisions=[
            {
                "candidate_id": arbiter_candidate_id,
                "reviewer": "codex",
                "verdict": "prefer",
                "rationale": "bounded escalation improves synthesis quality",
            }
        ],
    )
    assert_true(arbiter_updated.get("status") == "accepted", "preferred arbiter decision should accept consensus")
    assert_true((arbiter_updated.get("arbiter") or {}).get("status") == "resolved", "arbiter decision should resolve arbiter state")
    assert_true(arbiter_updated.get("selected_candidate_id") == arbiter_candidate_id, "arbiter should be able to select an explicit candidate")
    assert_true(
        arbiter_session.get("trajectory") and arbiter_session["trajectory"][-1].get("event_type") == "arbiter_decision",
        "session trajectory should record arbiter decisions",
    )

    reviewer_session = _build_workflow_run_session(
        query="Validate reviewer-gated consensus behavior",
        data={"blueprint_id": "nixos-service-hardening"},
        selected_blueprint=blueprints.get("nixos-service-hardening"),
        orchestration=default_ctx,
        lesson_refs=[],
    )
    reviewer_consensus = reviewer_session.get("consensus") or {}
    updated = _apply_consensus_update(
        reviewer_session,
        selected_candidate_id=str(reviewer_consensus.get("selected_candidate_id") or ""),
        decisions=[
            {
                "candidate_id": str(reviewer_consensus.get("selected_candidate_id") or ""),
                "reviewer": "codex",
                "verdict": "accept",
                "rationale": "best fit for the requested workflow",
            }
        ],
        summary="reviewer accepted the seeded primary candidate",
    )
    assert_true(updated.get("status") == "accepted", "accepted reviewer decision should accept consensus")
    assert_true(len(updated.get("history") or []) == 1, "consensus history should record the decision")
    assert_true(reviewer_session.get("trajectory") and reviewer_session["trajectory"][-1].get("event_type") == "consensus_update", "session trajectory should record consensus updates")
    reviewer_team = _build_orchestration_team(hardening_policy, default_ctx, reviewer_consensus)
    assert_true(reviewer_team.get("active_slots") == ["primary", "reviewer"], "reviewer-gated team should stay local and bounded")

    evaluation_registry = _default_agent_evaluations_registry()
    evaluation_registry = _record_agent_review_event(
        evaluation_registry,
        agent="claude",
        profile="remote-reasoning",
        passed=True,
        score=0.92,
        reviewer="codex",
        review_type="acceptance",
        task_class="remote_reasoning_escalation",
        ts=1,
    )
    evaluation_registry = _record_agent_consensus_event(
        evaluation_registry,
        agent="claude",
        lane="reasoning",
        selected_candidate_id="primary",
        summary="selected for the reasoning lane",
        ts=2,
    )
    evaluation_registry = _record_agent_runtime_event(
        evaluation_registry,
        agent="claude",
        profile="reasoning",
        event_type="completed",
        risk_class="safe",
        approved=True,
        token_delta=120,
        tool_call_delta=2,
        detail="completed reasoning workflow cleanly",
        ts=3,
    )
    claude = (evaluation_registry.get("agents") or {}).get("claude") or {}
    reasoning = (claude.get("profiles") or {}).get("reasoning") or {}
    remote_reasoning = (claude.get("profiles") or {}).get("remote-reasoning") or {}
    assert_true(remote_reasoning.get("accepted_reviews") == 1, "review event should accumulate accepted reviews")
    assert_true(reasoning.get("consensus_selected") == 1, "consensus event should accumulate selection counts")
    assert_true(reasoning.get("runtime_events") == 1, "runtime event should accumulate execution history")
    assert_true(float(reasoning.get("average_runtime_score", 0.0) or 0.0) > 0.0, "runtime event should preserve execution quality")
    assert_true((evaluation_registry.get("summary") or {}).get("agent_count") >= 1, "evaluation summary should track agent count")

    with tempfile.TemporaryDirectory(prefix="agent-evals-") as tmp_dir:
        eval_path = Path(tmp_dir) / "agent-evaluations.json"
        os.environ["DATA_DIR"] = tmp_dir
        seeded_registry = _default_agent_evaluations_registry()
        seeded_registry = _record_agent_review_event(
            seeded_registry,
            agent="human",
            profile="reasoning",
            passed=True,
            score=1.0,
            reviewer="codex",
            review_type="acceptance",
            task_class="remote_reasoning_escalation",
            ts=3,
        )
        seeded_registry = _record_agent_consensus_event(
            seeded_registry,
            agent="human",
            lane="reasoning",
            selected_candidate_id="primary",
            summary="historically preferred for reasoning",
            ts=4,
        )
        seeded_registry = _record_agent_runtime_event(
            seeded_registry,
            agent="human",
            profile="reasoning",
            event_type="completed",
            risk_class="safe",
            approved=True,
            token_delta=42,
            tool_call_delta=1,
            detail="historically successful reasoning run",
            ts=5,
        )
        import asyncio
        asyncio.run(_save_agent_evaluations_registry(seeded_registry))
        reloaded = _load_agent_evaluations_registry_sync()
        assert_true((reloaded.get("summary") or {}).get("consensus_events", 0) >= 1, "reloaded registry should preserve consensus history")
        assert_true((reloaded.get("summary") or {}).get("runtime_events", 0) >= 1, "reloaded registry should preserve runtime history")
        seeded_consensus = _seed_agent_evaluation(reasoning_policy, default_ctx)
        candidates = seeded_consensus.get("candidates") or []
        primary = next((item for item in candidates if item.get("candidate_id") == "primary"), {})
        assert_true(
            float((primary.get("history_bias") or {}).get("review_score", 0.0)) > 0.0,
            "historical review score should feed back into future candidate scoring",
        )
        assert_true(
            float((primary.get("history_bias") or {}).get("selection_score", 0.0)) > 0.0,
            "historical selection count should feed back into future candidate scoring",
        )
        assert_true(
            float((primary.get("history_bias") or {}).get("runtime_score", 0.0)) > 0.0,
            "historical runtime quality should feed back into future candidate scoring",
        )
        os.environ.pop("DATA_DIR", None)

    print("PASS: workflow orchestration defaults keep top-level agents as orchestrators and sub-agents bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
