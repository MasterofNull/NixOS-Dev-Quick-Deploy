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
approval_policy = "never"
approvals_reviewer = "auto_review"
sandbox_mode = "danger-full-access"

[sandbox_workspace_write]
network_access = false
writable_roots = ["/"]
exclude_slash_tmp = true
exclude_tmpdir_env_var = true

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

        def project(text: str) -> tuple[str, dict]:
            if not text:
                seed = re.search(r"printf '([^']+)' > \"\$codex_cfg\"", base)
                assert seed is not None, "fresh Codex config must seed a TOML document"
                text = seed.group(1).replace("\\n", "\n")
            source.write_text(text, encoding="utf-8")
            proc = subprocess.run(
                [yq, "-p", "toml", "-o", "toml", transform, str(source)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            if proc.returncode != 0:
                raise AssertionError(f"actual Codex yq transform failed: {proc.stderr.strip()}")
            parsed = tomllib.loads(proc.stdout)
            assert parsed["approval_policy"] == "on-request"
            assert parsed["approvals_reviewer"] == "user"
            assert parsed["model_auto_compact_token_limit"] == 50000
            return proc.stdout, parsed

        output, projected = project(fixture)
        assert project(output)[1] == projected, "Codex projection must be idempotent"
        fresh_output, fresh = project("")
        assert project(fresh_output)[1] == fresh
        expected_sandbox = {
            "network_access": True,
            "writable_roots": ["/workspace/NixOS-Dev-Quick-Deploy"],
            "exclude_slash_tmp": False,
            "exclude_tmpdir_env_var": False,
        }
        for parsed in (fresh, projected):
            assert parsed["sandbox_mode"] == "workspace-write"
            assert parsed["sandbox_workspace_write"] == expected_sandbox

        for modern_fixture in (
            'default_permissions = ":workspace"\n',
            '[permissions.custom]\nextends = ":workspace"\n'
            '[permissions.custom.network]\nenabled = false\n',
            'default_permissions = "custom"\n'
            '[permissions.custom]\nextends = ":workspace"\n'
            '[permissions.custom.network]\nenabled = true\n',
        ):
            original = tomllib.loads(modern_fixture)
            modern_output, modern = project(modern_fixture)
            assert "sandbox_mode" not in modern
            assert "sandbox_workspace_write" not in modern
            for key in ("permissions", "default_permissions"):
                assert modern.get(key) == original.get(key)
            assert project(modern_output)[1] == modern

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
