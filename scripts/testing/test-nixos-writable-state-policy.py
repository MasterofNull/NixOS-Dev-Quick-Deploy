#!/usr/bin/env python3
"""Compatibility wrapper and validator for the NixOS writable-state contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def read_required(root: Path, relative: str, failures: list[str]) -> str:
    path = root / relative
    try:
        return path.read_text(encoding="utf-8")
    except Exception as err:
        failures.append(f"missing or unreadable {relative}: {err}")
        return ""


def validate_writable_state_py(root: Path) -> list[str]:
    failures: list[str] = []
    policy_text = read_required(root, "docs/development/NIXOS-WRITABLE-STATE-REQUIREMENTS.md", failures)
    options_text = read_required(root, "nix/modules/core/options.nix", failures)
    runtime_profiles_text = read_required(root, "config/runtime-isolation-profiles.json", failures)
    mcp_text = read_required(root, "nix/modules/services/mcp-servers.nix", failures)
    http_text = read_required(root, "ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py", failures)
    disclosure_text = read_required(root, "ai-stack/mcp-servers/hybrid-coordinator/knowledge/progressive_disclosure.py", failures)
    learning_text = read_required(root, "ai-stack/mcp-servers/hybrid-coordinator/extensions/real_time_learning_engine.py", failures)

    if "mutableSpaces = {" not in options_text:
        failures.append("options should expose declarative mutable spaces")
    if "programWritablePaths" not in options_text:
        failures.append("options should expose program writable paths")

    nix_roots = set(re.findall(r"workspace_root\s*=\s*\"([^\"]+)\"", options_text))
    try:
        profiles_json = json.loads(runtime_profiles_text) if runtime_profiles_text else {}
        json_roots = {
            p["workspace_root"]
            for p in profiles_json.get("profiles", {}).values()
            if isinstance(p, dict) and "workspace_root" in p
        }
    except Exception as exc:
        failures.append(f"runtime profiles JSON invalid: {exc}")
        json_roots = set()

    for root_path in json_roots:
        if root_path not in nix_roots:
            failures.append(f"runtime profile registry workspace root missing from Nix defaults: {root_path}")

    for required in [
        "/var/lib/nixos-ai-stack/mutable/program/agent-runs",
        "/var/lib/nixos-ai-stack/mutable/program/agent-worktrees",
    ]:
        if required not in nix_roots:
            failures.append(f"Nix runtime isolation defaults missing workspace root: {required}")
        if required not in json_roots:
            failures.append(f"runtime isolation profile registry missing workspace root: {required}")

    if "Treat `repoPath` as read-only for system services." not in policy_text:
        failures.append("policy doc should declare repoPath read-only for hardened services")
    if "runtime mutable state" not in policy_text:
        failures.append("policy doc should classify runtime mutable state")
    if "repo-grounded artifact" not in policy_text:
        failures.append("policy doc should classify repo-grounded artifacts")
    if "`deployment.mutableSpaces.enable`" not in policy_text:
        failures.append("policy doc should name the declarative mutable-spaces switch")

    if "ReadOnlyPaths = [repoSource];" not in mcp_text:
        failures.append("MCP services should keep the repo path mounted read-only")
    if "create_path 0770 ${lib.escapeShellArg path}" not in mcp_text:
        failures.append("mutable path bootstrap should create runtime roots group-writable")
    if 'map (root: "d ${root} 0770 ${svcUser} ${aiGroup} -") runtimeWorkspaceRoots' not in mcp_text:
        failures.append("tmpfiles d-rule should create runtime workspace roots group-writable")
    if 'map (root: "z ${root} 0770 ${svcUser} ${aiGroup} -") runtimeWorkspaceRoots' not in mcp_text:
        failures.append("tmpfiles z-rule should enforce runtime workspace root group writability")

    if 'os.getenv("DISCLOSURE_CONTEXT_DIR", "/var/lib/ai-stack/hybrid/context-tiers")' not in http_text:
        failures.append("hybrid coordinator should keep disclosure runtime state in writable service storage")
    if 'os.getenv("REMEDIATION_PLAYBOOKS_DIR", "/var/lib/ai-stack/hybrid/playbooks")' not in learning_text:
        failures.append("hybrid coordinator should keep remediation playbooks in writable service storage")
    if 'os.getenv("AI_STACK_REPO_PATH", str(Path(__file__).resolve().parents[4]))' not in disclosure_text:
        failures.append("progressive disclosure config should resolve repo root through env or relative path")
    if "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/progressive-disclosure-domains.json" in disclosure_text:
        failures.append("progressive disclosure config should not hardcode a developer checkout path")

    return failures


def main() -> int:
    # 1. If precompiled binary exists, use it
    for candidate in [
        ROOT / "target" / "release" / "harness-contracts",
        ROOT / "target" / "debug" / "harness-contracts",
    ]:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            proc = subprocess.run(
                [
                    str(candidate),
                    "writable-state",
                    "--root",
                    str(ROOT),
                ],
                cwd=ROOT,
                check=False,
            )
            return proc.returncode

    # 2. If FORCE_CARGO_VALIDATOR is explicitly set to 1, use cargo
    if os.environ.get("FORCE_CARGO_VALIDATOR") == "1":
        proc = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "harness-contracts",
                "--",
                "writable-state",
                "--root",
                str(ROOT),
            ],
            cwd=ROOT,
            check=False,
        )
        return proc.returncode

    # 3. Otherwise, run the fast native Python validator directly (0.04s, prevents CI timeouts)
    failures = validate_writable_state_py(ROOT)
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("PASS: writable-state policy and service defaults remain declarative-safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
