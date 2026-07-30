#!/usr/bin/env python3
"""Validate that admitted MCPs reach the native Claude and Codex config stores."""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]
HOME_BASE = ROOT / "nix" / "home" / "base.nix"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def extract_codex_yq_transform(base: str) -> str:
    match = re.search(
        r"""\$\{pkgs\.yq-go\}/bin/yq -p toml -o toml '\n(?P<transform>.*?)\n    ' "\$codex_cfg" > "\$codex_tmp\"""",
        base,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError("could not extract the Home Manager Codex yq transform")
    return (
        match.group("transform")
        .replace("${repoPath}", "/workspace/NixOS-Dev-Quick-Deploy")
        .replace("${toString aiHybridPort}", "8003")
        .replace("${toString aiAidbPort}", "8002")
    )


def test_codex_yq_transform(base: str) -> None:
    yq = shutil.which("yq")
    if yq is None:
        raise AssertionError("MISSING_TOOL: yq is required to validate the actual Codex projection")

    fixture = """
sentinel = "preserve"

[features]
codex_hooks = true
hooks = false
other_feature = true

[projects."/"]
trust_level = "trusted"

[projects."/existing"]
trust_level = "untrusted"

[mcp_servers.existing]
command = "preserve-me"
"""
    transform = extract_codex_yq_transform(base)
    with tempfile.TemporaryDirectory(prefix="agent-mcp-projection-") as temp_dir:
        source = Path(temp_dir) / "input.toml"
        source.write_text(fixture, encoding="utf-8")
        proc = subprocess.run(
            [yq, "-p", "toml", "-o", "toml", transform, str(source)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    if proc.returncode != 0:
        raise AssertionError(f"actual Codex yq transform failed: {proc.stderr.strip()}")
    projected = tomllib.loads(proc.stdout)

    assert projected["sentinel"] == "preserve"
    assert projected["features"]["hooks"] is True
    assert projected["features"]["other_feature"] is True
    assert "codex_hooks" not in projected["features"]
    assert "/" not in projected["projects"]
    assert projected["projects"]["/existing"]["trust_level"] == "untrusted"
    assert (
        projected["projects"]["/workspace/NixOS-Dev-Quick-Deploy"]["trust_level"]
        == "trusted"
    )
    assert projected["mcp_servers"]["existing"]["command"] == "preserve-me"
    assert projected["mcp_servers"]["hybrid-coordinator"]["command"] == "python3"
    assert projected["mcp_servers"]["hybrid-coordinator"]["env"]["HYBRID_URL"].endswith(
        ":8003"
    )
    assert projected["mcp_servers"]["hybrid-coordinator"]["env"]["AIDB_URL"].endswith(
        ":8002"
    )
    assert projected["mcp_servers"]["osint-tools"]["default_tools_approval_mode"] == "prompt"
    assert (
        projected["mcp_servers"]["openaiDeveloperDocs"]["default_tools_approval_mode"]
        == "auto"
    )


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
        ".features.hooks = true",
        "Codex reconciliation must enable the supported hooks feature key",
    )
    require(
        base,
        'del(.projects."/")',
        "Codex reconciliation must not trust every filesystem project through '/'",
    )
    require(
        base,
        '.projects."${repoPath}".trust_level = "trusted"',
        "Codex reconciliation must explicitly trust only the configured repository path",
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
    test_codex_yq_transform(base)

    print("PASS: native Claude and Codex MCP projections are declared and executable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
