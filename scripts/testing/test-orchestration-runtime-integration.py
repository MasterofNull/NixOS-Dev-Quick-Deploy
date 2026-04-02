#!/usr/bin/env python3
"""Static regression checks for orchestration runtime integration in workflow APIs."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

    assert_true(
        "from orchestration import (" in text
        and "AgentHQ," in text
        and "DelegationAPI," in text
        and "WorkspaceManager," in text
        and "MCPToolInvoker," in text
        and "IsolationMode," in text
        and "ToolStatus," in text,
        "workflow runtime should import live orchestration framework components for integration mapping",
    )
    assert_true(
        "def _build_orchestration_runtime_contract(session: Dict[str, Any]) -> Dict[str, Any]:" in text,
        "workflow runtime should define orchestration runtime integration metadata",
    )
    assert_true(
        'session["orchestration_runtime"] = _build_orchestration_runtime_contract(session)' in text,
        "workflow runtime should refresh orchestration integration metadata during session normalization",
    )
    assert_true(
        '"orchestration_runtime": sess.get("orchestration_runtime", {})' in text,
        "workflow session listing should expose orchestration runtime integration metadata",
    )
    assert_true(
        '"orchestration_runtime": session.get("orchestration_runtime", {})' in text,
        "detailed team inspection should expose orchestration runtime integration metadata",
    )
    assert_true(
        'return IsolationMode.GIT_WORKTREE.value' in text and 'return IsolationMode.COPY.value' in text and 'return IsolationMode.TEMP_DIR.value' in text,
        "workflow runtime should map isolation state onto orchestration workspace modes",
    )
    assert_true(
        '"status": ToolStatus.AVAILABLE.value' in text,
        "workflow runtime should expose integrated tool invocation status",
    )
    assert_true(
        '_AGENT_HQ = AgentHQ(' in text
        and '_DELEGATION_API = DelegationAPI()' in text
        and '_WORKSPACE_MANAGER = WorkspaceManager(' in text
        and '_MCP_TOOL_INVOKER = MCPToolInvoker(cache_enabled=True)' in text,
        "workflow runtime should instantiate live orchestration framework services once",
    )
    assert_true(
        '"framework_status": "live"' in text
        and '"live_session": hq_session is not None' in text
        and '"queue_size": delegation_status.get("queue_size", 0)' in text
        and '"active_workspaces": len(workspace_list)' in text
        and '"registered_tools": tool_report.get("tools_registered", 0)' in text,
        "workflow runtime contract should expose live orchestration health and usage signals",
    )

    print("PASS: orchestration runtime integration is wired into workflow session APIs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
