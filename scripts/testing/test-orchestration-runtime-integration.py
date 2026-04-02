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
        "from orchestration import IsolationMode, ToolStatus" in text,
        "workflow runtime should import orchestration framework enums for integration mapping",
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

    print("PASS: orchestration runtime integration is wired into workflow session APIs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
