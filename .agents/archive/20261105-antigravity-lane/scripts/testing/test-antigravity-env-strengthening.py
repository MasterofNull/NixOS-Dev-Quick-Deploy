#!/usr/bin/env python3
"""
test-antigravity-env-strengthening.py — Test suite validating Antigravity/Gemini environment,
tooling, MCP, hooks, skills discovery, and role parity.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

def test_mcp_configs():
    print("Testing Antigravity MCP configurations...")
    configs = [
        Path.home() / ".gemini" / "config" / "mcp_config.json",
        REPO / ".agents" / "mcp_config.json",
        Path.home() / ".gemini" / "antigravity" / "mcp_config.json",
    ]
    for p in configs:
        assert p.exists(), f"Missing MCP config: {p}"
        with open(p) as f:
            cfg = json.load(f)
        servers = cfg.get("mcpServers", {})
        assert "lean-ctx" in servers, f"'lean-ctx' missing in {p}"
        assert servers["lean-ctx"].get("args") == ["mcp"], f"'lean-ctx' args must be ['mcp'] in {p}"
        assert "hybrid-coordinator" in servers, f"'hybrid-coordinator' missing in {p}"
        hc_args = servers["hybrid-coordinator"].get("args", [])
        assert any("mcp-bridge-hybrid.py" in arg for arg in hc_args), f"hybrid-coordinator missing bridge script in {p}"

    # Also check settings.json
    settings_p = Path.home() / ".gemini" / "settings.json"
    if settings_p.exists():
        with open(settings_p) as f:
            s = json.load(f)
        if "lean-ctx" in s.get("mcpServers", {}):
            assert s["mcpServers"]["lean-ctx"].get("args") == ["mcp"], "settings.json lean-ctx missing ['mcp'] args"
    print("  PASS: MCP configs valid and aligned across all locations.")

def test_antigravity_hooks():
    print("Testing Antigravity PreToolUse hook...")
    hook_script = Path.home() / ".gemini" / "hooks" / "lean-ctx-rewrite-antigravity.py"
    assert hook_script.exists(), f"Missing hook script: {hook_script}"
    assert os.access(hook_script, os.X_OK), f"Hook script not executable: {hook_script}"

    # Test rewrite of git status
    in_git = json.dumps({"toolCall": {"name": "run_command", "args": {"CommandLine": "git status"}}})
    p = subprocess.run([sys.executable, str(hook_script)], input=in_git, text=True, capture_output=True)
    assert p.returncode == 0, f"Hook failed: {p.stderr}"
    res = json.loads(p.stdout)
    assert res.get("decision") == "allow"
    assert "CommandLine" in res.get("overwrite", {})
    assert "lean-ctx -c 'git status'" in res["overwrite"]["CommandLine"]

    # Test passthrough of already lean-ctx command
    in_lean = json.dumps({"toolCall": {"name": "run_command", "args": {"CommandLine": "lean-ctx -c 'git status'"}}})
    p = subprocess.run([sys.executable, str(hook_script)], input=in_lean, text=True, capture_output=True)
    assert p.returncode == 0
    res = json.loads(p.stdout)
    assert res.get("decision") == "allow"
    assert "overwrite" not in res

    # Verify hooks.json in global and workspace
    for h_path in [Path.home() / ".gemini" / "config" / "hooks.json", REPO / ".agents" / "hooks.json"]:
        assert h_path.exists(), f"Missing hooks.json at {h_path}"
        with open(h_path) as f:
            h_data = json.load(f)
        assert "PreToolUse" in h_data
        matchers = [g.get("matcher") for g in h_data["PreToolUse"]]
        assert "run_command" in matchers

    print("  PASS: Antigravity PreToolUse hooks rewrite correctly and pass through.")

def test_skills_and_rules():
    print("Testing Skills and Rules discovery...")
    skills_json = REPO / ".agents" / "skills.json"
    assert skills_json.exists(), "Missing .agents/skills.json"
    with open(skills_json) as f:
        sj = json.load(f)
    entries = [e.get("path") for e in sj.get("entries", [])]
    assert ".agent/skills" in entries, ".agent/skills not in .agents/skills.json entries"

    rules_dir = REPO / ".agents" / "rules"
    assert (rules_dir / "lean-ctx.md").exists(), "Missing .agents/rules/lean-ctx.md"
    assert (rules_dir / "gemini-orchestrator.md").exists(), "Missing .agents/rules/gemini-orchestrator.md"

    gemini_md = REPO / ".agent" / "GEMINI.md"
    sz = gemini_md.stat().st_size
    assert sz < 24000, f".agent/GEMINI.md size {sz} exceeds limit 24,000 bytes"
    content = gemini_md.read_text()
    assert "Orchestrator and Reviewer" in content, "GEMINI.md must state Orchestrator and Reviewer role"
    assert "Cheapest-Eligible Implementer" in content, "GEMINI.md must mandate Rule 17"
    assert "lean-ctx" in content, "GEMINI.md must mandate lean-ctx"

    print("  PASS: Skills, rules, and GEMINI.md within limits and correctly configured.")

def test_role_and_delegation_parity():
    print("Testing role and delegation parity...")
    # Check lane eligibility registry
    reg_path = REPO / "config" / "lane-eligibility-registry.json"
    with open(reg_path) as f:
        reg = json.load(f)
    assert "rsi" in reg.get("roles", []), "'rsi' missing from lane-eligibility-registry.json roles"
    assert "rsi" in reg["lanes"]["gemini"]["eligible"], "'rsi' not in eligible roles for gemini lane"

    # Check shared llm_config.py
    llm_cfg = (REPO / "ai-stack" / "mcp-servers" / "shared" / "llm_config.py").read_text()
    assert '"rsi"' in llm_cfg, "'rsi' role missing from ROLE_SYSTEM_PROMPTS"

    # Check aq-antigravity-agent
    agent_py = (REPO / "scripts" / "ai" / "aq-antigravity-agent").read_text()
    assert '"rsi"' in agent_py, "'rsi' mode missing from aq-antigravity-agent"

    # Check aq-antigravity-inbox role confinement
    inbox_py = (REPO / "scripts" / "ai" / "aq-antigravity-inbox").read_text()
    assert '"rsi"' in inbox_py, "'rsi' missing from _IMPLEMENTATION_ROLES in aq-antigravity-inbox"

    print("  PASS: RSI role and delegation parity validated.")

def main():
    test_mcp_configs()
    test_antigravity_hooks()
    test_skills_and_rules()
    test_role_and_delegation_parity()
    print("\nALL ANTIGRAVITY ENVIRONMENT & TOOLING CHECKS PASSED!")

if __name__ == "__main__":
    main()
