#!/usr/bin/env python3
"""Static regression for workflow run policy override and worktree isolation support."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"
ISOLATION_PROFILES = ROOT / "config" / "runtime-isolation-profiles.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    http_text = HTTP_SERVER.read_text(encoding="utf-8")
    isolation_text = ISOLATION_PROFILES.read_text(encoding="utf-8")

    assert_true(
        'incoming_policy = data.get("orchestration_policy")' in http_text,
        "workflow run session builder should read request-level orchestration_policy",
    )
    assert_true(
        'effective_policy.update(incoming_policy)' in http_text,
        "workflow run session builder should allow request policy overrides over blueprint defaults",
    )
    assert_true(
        "_validate_orchestration_policy(\n        effective_policy," in http_text,
        "workflow run session builder should validate merged effective policy",
    )
    assert_true(
        '"worktree-guarded"' in isolation_text and '"/var/lib/nixos-ai-stack/mutable/program/agent-worktrees"' in isolation_text,
        "runtime isolation profiles should expose a worktree-backed guarded mode",
    )

    print("PASS: workflow runs support request policy overrides and worktree isolation profile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
