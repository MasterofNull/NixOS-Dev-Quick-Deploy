#!/usr/bin/env python3
"""Static contract checks for the hybrid coordinator A2A compatibility layer."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"
OPENAI_A2A_HANDLERS = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "openai_a2a_handlers.py"


def assert_contains(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise AssertionError(message)


def main() -> int:
    http_server_source = HTTP_SERVER.read_text(encoding="utf-8")
    source = OPENAI_A2A_HANDLERS.read_text(encoding="utf-8")

    assert_contains(source, 'http_app.router.add_get("/.well-known/agent.json", handle_well_known_a2a)', "missing A2A well-known route")
    assert_contains(source, 'http_app.router.add_post("/a2a", handle_a2a_rpc)', "missing A2A RPC route")
    assert_contains(source, 'http_app.router.add_get("/a2a/tasks/{session_id}/events", handle_a2a_task_events)', "missing A2A task-events route")
    assert_contains(http_server_source, 'openai_a2a_handlers.register_routes(http_app)', "http_server should register extracted OpenAI/A2A routes")

    assert_contains(source, 'def _build_a2a_agent_card(base_url: str) -> Dict[str, Any]:', "missing A2A agent card helper")
    assert_contains(source, '"protocolVersion": "0.3.0"', "agent card should declare protocol version")
    assert_contains(source, '"pushNotifications": False', "agent card should declare push notification support")
    assert_contains(source, '"stateTransitionHistory": True', "agent card should expose task history capability")

    assert_contains(source, 'if method in {"message/send", "message/stream"}:', "missing A2A message/send + stream handler")
    assert_contains(source, 'if method == "tasks/get":', "missing A2A tasks/get handler")
    assert_contains(source, 'if method == "tasks/list":', "missing A2A tasks/list handler")
    assert_contains(source, 'if method == "tasks/cancel":', "missing A2A tasks/cancel handler")
    assert_contains(source, '"pushNotifications": False', "push notification boundary must stay explicit")
    assert_contains(source, '"endpoint": f"{origin}/"', "agent card should expose root JSON-RPC endpoint")
    assert_contains(source, '"taskEvents": f"{origin}/a2a/tasks/{{taskId}}/events"', "agent card should expose task events endpoint")
    assert_contains(source, 'def _session_to_a2a_artifacts(session: Dict[str, Any]) -> List[Dict[str, Any]]:', "missing task artifact projection helper")
    assert_contains(source, '"kind": "artifact-update"', "missing artifact update payload")
    assert_contains(source, '"kind": "status-update"', "missing status update payload")

    assert_contains(source, 'event: task\\ndata:', "missing task SSE event")
    assert_contains(source, 'event: status-update\\ndata:', "missing status update SSE event")
    assert_contains(source, 'event: artifact-update\\ndata:', "missing artifact update SSE event")

    print("PASS: hybrid coordinator A2A compatibility source contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
