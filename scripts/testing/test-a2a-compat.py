#!/usr/bin/env python3
"""Static contract checks for the hybrid coordinator A2A compatibility layer."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_contains(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise AssertionError(message)


def main() -> int:
    source = HTTP_SERVER.read_text(encoding="utf-8")

    assert_contains(source, 'http_app.router.add_get("/.well-known/agent.json", handle_well_known_a2a)', "missing A2A well-known route")
    assert_contains(source, 'http_app.router.add_post("/a2a", handle_a2a_rpc)', "missing A2A RPC route")
    assert_contains(source, 'http_app.router.add_get("/a2a/tasks/{session_id}/events", handle_a2a_task_events)', "missing A2A task-events route")

    assert_contains(source, 'def _build_a2a_agent_card(base_url: str) -> Dict[str, Any]:', "missing A2A agent card helper")
    assert_contains(source, '"protocolVersion": "0.3.0"', "agent card should declare protocol version")
    assert_contains(source, '"pushNotifications": False', "agent card should declare push notification support")
    assert_contains(source, '"stateTransitionHistory": True', "agent card should expose task history capability")

    assert_contains(source, 'if method == "message/send":', "missing A2A message/send handler")
    assert_contains(source, 'if method == "tasks/get":', "missing A2A tasks/get handler")
    assert_contains(source, 'if method == "tasks/list":', "missing A2A tasks/list handler")
    assert_contains(source, 'if method == "tasks/cancel":', "missing A2A tasks/cancel handler")

    assert_contains(source, 'event: task.snapshot', "missing task snapshot SSE event")
    assert_contains(source, 'event: task.event', "missing task event SSE event")

    print("PASS: hybrid coordinator A2A compatibility source contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
