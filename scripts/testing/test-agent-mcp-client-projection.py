#!/usr/bin/env python3
"""Validate that admitted MCPs reach the native Claude and Codex config stores."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOME_BASE = ROOT / "nix" / "home" / "base.nix"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def main() -> int:
    base = HOME_BASE.read_text(encoding="utf-8")

    require(
        base,
        "home.activation.reconcileAgentMcpClients",
        "Home Manager must reconcile native agent MCP configuration stores",
    )
    require(
        base,
        '.mcpServers["hybrid-coordinator"]',
        "Claude user config must receive the hybrid coordinator MCP",
    )
    require(
        base,
        '.mcpServers["osint-tools"]',
        "Claude user config must receive the OSINT MCP",
    )
    require(
        base,
        ".mcpServers.github",
        "Claude and shared MCP config must receive the read-only GitHub wrapper",
    )
    require(
        base,
        "del(.features.codex_hooks)",
        "Codex reconciliation must remove the deprecated codex_hooks feature key",
    )
    require(
        base,
        '.mcp_servers."hybrid-coordinator"',
        "Codex config must receive the hybrid coordinator MCP",
    )
    require(
        base,
        '.mcp_servers."osint-tools"',
        "Codex config must receive the OSINT MCP",
    )
    require(
        base,
        ".mcp_servers.openaiDeveloperDocs",
        "Codex config must receive the official OpenAI developer docs MCP",
    )
    require(
        base,
        '"HYBRID_URL": "http://127.0.0.1:${toString aiHybridPort}"',
        "MCP projections must derive the coordinator port from the Nix port registry",
    )
    require(
        base,
        '"AIDB_URL": "http://127.0.0.1:${toString aiAidbPort}"',
        "MCP projections must derive the AIDB port from the Nix port registry",
    )

    print("PASS: native Claude and Codex MCP projections are declared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
