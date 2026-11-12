#!/usr/bin/env python3
"""Static regression for workflow run policy override and worktree isolation support."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"
ISOLATION_PROFILES = ROOT / "config" / "runtime-isolation-profiles.json"


# Explicit live owners of the asserted behavior; coordinator_source() fails if http_server_impl.py
# (first entry) does not reference an owner module, so dormant files cannot satisfy assertions.
COORDINATOR_OWNERS = (
    "http_server_impl.py",
    "core/session_builders.py",
    "middleware/auth.py",
)


def coordinator_source() -> str:
    root = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
    http_text = (root / COORDINATOR_OWNERS[0]).read_text(encoding="utf-8")
    for owner in COORDINATOR_OWNERS[1:]:
        if Path(owner).stem not in http_text:
            raise AssertionError(f"{owner} is not referenced by {COORDINATOR_OWNERS[0]}; owner is not wired")
    return "\n".join((root / owner).read_text(encoding="utf-8") for owner in COORDINATOR_OWNERS)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    http_text = coordinator_source()
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
