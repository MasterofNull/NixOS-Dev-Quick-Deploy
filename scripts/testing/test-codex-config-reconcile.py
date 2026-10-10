#!/usr/bin/env python3
"""Exercise the Home Manager Codex projection without touching the user's config."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    source = (ROOT / "nix/home/base.nix").read_text()
    expression = re.search(
        r"\$\{pkgs\.yq-go\}/bin/yq -p toml -o toml '(.*?)' \"\$codex_cfg\"",
        source,
        re.DOTALL,
    )
    assert expression, "Codex reconciliation producer not found"
    transform = expression.group(1)
    for key, value in {
        "${repoPath}": str(ROOT),
        "${toString aiHybridPort}": "12345",
        "${toString aiAidbPort}": "12346",
    }.items():
        transform = transform.replace(key, value)
    assert "${" not in transform, "unhandled Nix interpolation"
    yq = shutil.which("yq")
    codex = shutil.which("codex")
    assert yq and codex, "installed yq-go and Codex required"

    def project(text: str) -> str:
        return subprocess.run(
            [yq, "-p", "toml", "-o", "toml", transform],
            input=text, text=True, capture_output=True, check=True,
        ).stdout

    fixtures = {
        "clean": 'approval_policy = "on-request"\n',
        "legacy": '''model = "gpt-5.6-sol"
approval_policy = "never"
[features]
codex_hooks = true
[projects."/"]
trust_level = "trusted"
[sandbox_workspace_write]
writable_roots = ["/", "/home"]
network_access = false
[mcp_servers.custom]
command = "custom-tool"
''',
        "modern": '''default_permissions = "restricted"
[permissions.restricted]
[permissions.restricted.network]
enabled = false
''',
        "permissions_only": '''[permissions.restricted]
[permissions.restricted.network]
enabled = false
''',
    }
    with tempfile.TemporaryDirectory(prefix="codex-reconcile-") as temporary:
        for label, fixture in fixtures.items():
            original = tomllib.loads(fixture)
            rendered = project(fixture)
            result = tomllib.loads(rendered)
            assert tomllib.loads(project(rendered)) == result, label + " is not idempotent"
            assert result["approval_policy"] == "on-request"
            assert result["approvals_reviewer"] == "user"
            assert "/" not in result["projects"]
            assert result["projects"][str(ROOT)]["trust_level"] == "trusted"
            assert "codex_hooks" not in result["features"]
            assert result["features"]["hooks"] is True
            if "permissions" in original:
                assert result["permissions"] == original["permissions"]
                assert result.get("default_permissions") == original.get("default_permissions")
                assert "sandbox_mode" not in result
                assert "sandbox_workspace_write" not in result
            else:
                assert result["sandbox_mode"] == "workspace-write"
                sandbox = result["sandbox_workspace_write"]
                assert sandbox["network_access"] is True
                assert sandbox["writable_roots"] == [str(ROOT)]
                assert sandbox["exclude_slash_tmp"] is False
                assert sandbox["exclude_tmpdir_env_var"] is False
            if label == "legacy":
                assert result["model"] == original["model"]
                assert result["mcp_servers"]["custom"] == original["mcp_servers"]["custom"]
            assert result["mcp_servers"]["hybrid-coordinator"]["default_tools_approval_mode"] == "writes"
            assert result["mcp_servers"]["osint-tools"]["default_tools_approval_mode"] == "prompt"
            home = Path(temporary) / label
            home.mkdir()
            (home / "config.toml").write_text(rendered)
            parsed = subprocess.run(
                [codex, "mcp", "list", "--json"], cwd=temporary,
                env={**os.environ, "CODEX_HOME": str(home)},
                text=True, capture_output=True,
            )
            if label == "permissions_only":
                assert parsed.returncode != 0 and "does not set `default_permissions`" in parsed.stderr
            else:
                assert parsed.returncode == 0, f"{label}: {parsed.stderr}"
            print(f"PASS: {label} projection, preservation, idempotence and Codex parse expectation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
