#!/usr/bin/env python3
"""Static regression checks for workflow-run orchestration default routing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HC = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
HTTP_SERVER = HC / "http_server_impl.py"
ORCHESTRATION_UTILS = HC / "workflow" / "orchestration_utils.py"
SESSION_BUILDERS = HC / "core" / "session_builders.py"
AGENT_REGISTRY = HC / "workflow" / "agent_registry.py"
RUNTIME_MANAGER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "runtime_manager.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = RUNTIME_MANAGER.read_text(encoding="utf-8")
    utils_text = ORCHESTRATION_UTILS.read_text(encoding="utf-8")
    http_text = HTTP_SERVER.read_text(encoding="utf-8")
    builders_text = SESSION_BUILDERS.read_text(encoding="utf-8")
    registry_text = AGENT_REGISTRY.read_text(encoding="utf-8")

    assert_true(
        "from runtime_manager import (" in http_text
        and "orchestration_utils" in text,
        "http server should load runtime_manager, which shares lane resolution with orchestration_utils",
    )

    assert_true(
        "def _default_orchestration_policy_for_query(query: str) -> Dict[str, Any]:" in text,
        "workflow runtime should derive orchestration defaults from the query",
    )
    assert_true(
        '_ai_coordinator_route_by_complexity(normalized_query, "", False)' in text,
        "workflow runtime should reuse ai-coordinator complexity routing for default policy seeding",
    )
    assert_true(
        '"primary_lane": "research"' in text
        and '"escalation_lane": "none"' in text
        and '"collaborator_lanes": ["diagnostics" if local_handoff else "implementation"]' in text,
        "planning and retrieval workflows should seed Gemini-oriented research with a local handoff lane and no default escalation slot",
    )
    assert_true(
        'if normalized_lane == "research":\n        return "gemini"' in utils_text,
        "research lanes should resolve to the Gemini agent by default",
    )
    assert_true(
        'if normalized_lane == "research":\n        return "remote-gemini"' in utils_text,
        "research lanes should advertise the remote-gemini profile",
    )
    assert_true(
        '"runtime_id": _ai_coordinator_default_runtime_id_for_profile(profile)' in utils_text,
        "workflow candidates should expose runtime ids for live inspection",
    )
    assert_true(
        '"profile": str(candidate.get("profile", "") or "").strip()' in utils_text
        and '"runtime_id": str(candidate.get("runtime_id", "") or "").strip()' in utils_text,
        "team members should expose profile and runtime id hints",
    )
    assert_true(
        '"selected_profile": str(consensus.get("selected_profile", "") or "").strip()' in builders_text
        and '"selected_runtime_id": str(consensus.get("selected_runtime_id", "") or "").strip()' in builders_text,
        "orchestration runtime contract should expose the selected profile and runtime id",
    )
    assert_true(
        '"prefer harness retrieval, memory recall, and periodic compaction over resending long prompt history"' in registry_text,
        "workflow runtime default intent contract should bias long-running work toward harness-side context offload",
    )
    assert_true(
        '"context strategy or blocker documented when the task is long-running"' in registry_text,
        "workflow runtime default intent contract should require a documented context strategy for long-running work",
    )

    print("PASS: workflow-run orchestration defaults seed Gemini and local handoff metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
