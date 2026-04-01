#!/usr/bin/env python3
"""Static regression checks for NixOS writable-state policy and service defaults."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROADMAP = ROOT / ".agents" / "plans" / "NEXT-GEN-AGENTIC-ROADMAP-2026-03.md"
POLICY_DOC = ROOT / "docs" / "development" / "NIXOS-WRITABLE-STATE-REQUIREMENTS.md"
MCP_SERVERS = ROOT / "nix" / "modules" / "services" / "mcp-servers.nix"
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"
DISCLOSURE = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "progressive_disclosure.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    roadmap_text = ROADMAP.read_text(encoding="utf-8")
    policy_text = POLICY_DOC.read_text(encoding="utf-8")
    mcp_text = MCP_SERVERS.read_text(encoding="utf-8")
    http_text = HTTP_SERVER.read_text(encoding="utf-8")
    disclosure_text = DISCLOSURE.read_text(encoding="utf-8")

    assert_true(
        "runtime mutable state must default to declarative writable roots" in roadmap_text,
        "roadmap should keep the writable-state rule in the scaffold closure program",
    )
    assert_true(
        "Treat `repoPath` as read-only for system services." in policy_text,
        "policy doc should declare repoPath read-only for hardened services",
    )
    assert_true(
        "runtime mutable state" in policy_text and "repo-grounded artifact" in policy_text,
        "policy doc should classify repo artifacts separately from runtime state",
    )
    assert_true(
        'ReadOnlyPaths            = [ mcp.repoPath ];' in mcp_text,
        "MCP services should keep the repo path mounted read-only",
    )
    assert_true(
        'os.getenv("DISCLOSURE_CONTEXT_DIR", "/var/lib/ai-stack/hybrid/context-tiers")' in http_text,
        "hybrid coordinator should keep disclosure runtime state in writable service storage",
    )
    assert_true(
        'os.getenv("REMEDIATION_PLAYBOOKS_DIR", "/var/lib/ai-stack/hybrid/playbooks")' in http_text,
        "hybrid coordinator should keep remediation playbooks in writable service storage",
    )
    assert_true(
        'os.getenv("AI_STACK_REPO_PATH", str(Path(__file__).resolve().parents[4]))' in disclosure_text,
        "progressive disclosure config should resolve repo root through env or relative path, not a hardcoded home path",
    )
    assert_true(
        "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/progressive-disclosure-domains.json" not in disclosure_text,
        "progressive disclosure config should not hardcode a developer checkout path",
    )

    print("PASS: writable-state policy and service defaults remain declarative-safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
