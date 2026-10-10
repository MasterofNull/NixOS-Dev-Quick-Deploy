#!/usr/bin/env python3
"""Validate enabled external MCP candidates stay pinned and bounded."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAYWRIGHT_LAUNCHER = ROOT / "scripts/ai/mcp-playwright-sandboxed"


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def assert_playwright_config(entry: dict) -> None:
    args = entry.get("args") or []
    joined = " ".join(args)
    assert "@playwright/mcp@0.0.76" in args, "Playwright MCP must be pinned"
    assert "@playwright/mcp@latest" not in joined, "Playwright MCP must not use @latest"
    assert "--allow-unrestricted-file-access" not in args, "unrestricted file access must remain disabled"
    assert "--no-sandbox" not in args, "browser sandbox must not be disabled"
    assert "--isolated" in args, "Playwright MCP must use isolated browser context"
    assert "--headless" in args, "Playwright MCP must run headless by default"
    assert "--block-service-workers" in args, "service workers must be blocked"
    assert "--allowed-origins" in args, "allowed origins must be explicit"


def assert_playwright_quarantined(candidate: dict) -> None:
    assert candidate["state"] == "quarantined", "Playwright must remain quarantined without enforce-mode confinement"
    assert candidate["review_status"] == "incomplete", "Playwright must not claim acceptance while confinement is unavailable"
    assert candidate["permissions"]["network"] is False, "quarantined Playwright must grant no network authority"
    assert candidate.get("blocked_reason"), "quarantined Playwright must explain its confinement block"
    assert candidate.get("unblock_condition"), "quarantined Playwright must define a future activation gate"

    launcher = PLAYWRIGHT_LAUNCHER.read_text(encoding="utf-8")
    assert "verify_apparmor_confinement" in launcher
    assert 'grep -Fqx "${APPARMOR_PROFILE} (enforce)" "${APPARMOR_PROFILES_PATH}" 2>/dev/null' in launcher
    assert 'exec aa-exec -p "${APPARMOR_PROFILE}" -- npx' in launcher
    assert "exec systemd-run --user" not in launcher, "unverified user-scope fallback must not execute Playwright"
    assert "verify_admission" in launcher
    assert 'candidate.get("state") == "enabled"' in launcher
    assert 'catalog.get("state") == "enabled"' in launcher

    admitted = subprocess.run(
        [str(PLAYWRIGHT_LAUNCHER), "--check-admission"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert admitted.returncode != 0, "quarantined Playwright must not pass the admission gate"
    assert "ADMISSION UNAVAILABLE" in admitted.stderr, admitted.stderr

    checked = subprocess.run(
        [str(PLAYWRIGHT_LAUNCHER), "--check-confinement"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert checked.returncode != 0, "current quarantined Playwright launcher must refuse unavailable confinement"
    assert "UNAVAILABLE" in checked.stderr, checked.stderr


def assert_semgrep_config(entry: dict) -> None:
    # Nix-provided `semgrep mcp`; the uvx semgrep-mcp package is deprecated upstream.
    env = entry.get("env") or {}
    assert entry.get("command") == "/run/current-system/sw/bin/semgrep", "Semgrep MCP must use the Nix system binary"
    assert entry.get("args") == ["mcp", "--transport", "stdio"], "Semgrep MCP must run `semgrep mcp` over stdio"
    assert "SEMGREP_APP_TOKEN" not in env, "Semgrep cloud token must not be configured"
    # Default tracing exports git user/repo/branch to Semgrep's collector.
    assert env.get("SEMGREP_MCP_DISABLE_TRACING") == "true", "Semgrep MCP tracing must be disabled"
    assert env.get("SEMGREP_SEND_METRICS") == "off", "Semgrep metrics must be off"


def assert_enabled_candidate(entry: dict, pinned_version: str) -> None:
    assert entry["state"] == "enabled"
    assert entry["pinned_version"] == pinned_version
    assert entry["review_status"] == "accepted-with-mitigations"
    assert entry.get("mitigations"), f"{entry['id']} must document mitigations"


def assert_understand_graph_complete() -> None:
    # The graph is a generated, untracked artifact: build it from the repo to prove the
    # producer works (deterministic, no LLM), instead of trusting whatever file is on disk.
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        graph = Path(tmp) / "knowledge-graph.json"
        subprocess.run([str(ROOT / "scripts/ai/aq-graph-build"), "--root", str(ROOT), "--out", str(graph)],
                       check=True, capture_output=True, timeout=300)
        payload = json.loads(graph.read_text(encoding="utf-8"))
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    metadata = payload.get("metadata") or {}
    assert nodes, "Understand-Anything graph must contain nodes"
    assert edges, "Understand-Anything graph must contain edges"
    assert metadata.get("total_nodes") == len(nodes), "graph node count must match tracked metadata"
    assert metadata.get("total_edges") == len(edges), "graph edge count must match tracked metadata"
    assert metadata.get("generator") == "aq-graph-build" and metadata.get("git_head"), \
        "graph must record its deterministic generator and source commit"


def main() -> int:
    claude = load_json(".claude/settings.json")
    gemini = load_json(".gemini/settings.json")
    continue_cfg = load_json("ai-stack/continue/config.json")
    registry = load_json("config/agent-capability-intake-candidates.json")

    assert_playwright_config(claude["mcpServers"]["playwright"])
    assert_playwright_config(gemini["mcpServers"]["Playwright MCP"])
    cont_pw = next(item for item in continue_cfg["mcpServers"] if item["name"] == "Playwright MCP")
    assert_playwright_config(cont_pw)
    assert_semgrep_config(load_json(".mcp.json")["mcpServers"]["semgrep"])
    assert_semgrep_config(claude["mcpServers"]["semgrep"])
    assert_semgrep_config(gemini["mcpServers"]["Semgrep MCP"])
    cont_semgrep = next(item for item in continue_cfg["mcpServers"] if item["name"] == "Semgrep MCP")
    assert_semgrep_config(cont_semgrep)

    candidates = {item["id"]: item for item in registry["candidates"]}
    assert_playwright_quarantined(candidates["playwright-mcp"])
    assert "@playwright/mcp@0.0.76" in candidates["playwright-mcp"]["install"]["args"]
    assert_enabled_candidate(candidates["github-mcp-readonly"], "0.20.2")
    assert candidates["github-mcp-readonly"]["install"]["args"][0] == "--read-only"
    assert candidates["github-mcp-readonly"]["permissions"]["writes"] is False
    assert_enabled_candidate(candidates["semgrep-mcp"], "nixpkgs")
    assert candidates["semgrep-mcp"]["install"]["args"] == ["mcp", "--transport", "stdio"]
    assert candidates["semgrep-mcp"]["permissions"]["secrets"] is False
    assert_enabled_candidate(candidates["mcp-admission-controller"], "local-2026-06-28")
    assert candidates["mcp-admission-controller"]["permissions"]["network"] is False
    assert candidates["mcp-admission-controller"]["permissions"]["secrets"] is False
    assert_enabled_candidate(candidates["trivy"], "0.66.0")
    assert "--skip-db-update" in candidates["trivy"]["install"]["args"]
    assert candidates["trivy"]["permissions"]["secrets"] is False
    assert_enabled_candidate(candidates["observability-query-skill"], "local-2026-06-28")
    assert candidates["observability-query-skill"]["install"]["command"] == "aq-report"
    assert candidates["observability-query-skill"]["permissions"]["network"] == "localhost"
    assert_enabled_candidate(candidates["nixos-specialist-tool-pack"], "statix-0.5.8+deadnix-1.3.1")
    assert candidates["nixos-specialist-tool-pack"]["install"]["command"] == "scripts/governance/nix-static-analysis.sh"
    assert_enabled_candidate(candidates["osv-scanner"], "2.2.4")
    assert candidates["osv-scanner"]["install"]["command"] == "osv-scanner"
    assert candidates["osv-scanner"]["permissions"]["secrets"] is False
    assert_enabled_candidate(candidates["syft-grype"], "syft-1.38.0+grype-0.104.1")
    assert candidates["syft-grype"]["install"]["command"] == "syft"
    assert candidates["syft-grype"]["permissions"]["secrets"] is False
    # partial: queries live, graph stale pending regeneration (Rule: catalog honesty)
    graph_layer = candidates["code-intelligence-graph-layer"]
    assert graph_layer["state"] == "partial"
    assert graph_layer["pinned_version"] == "understand-anything-54754a6+graph-2026-07-01"
    assert graph_layer["review_status"] == "accepted-with-mitigations"
    assert graph_layer.get("mitigations")
    assert graph_layer["tool_allowlist"] == ["graph_query"]
    assert_understand_graph_complete()

    print("PASS: enabled external MCP candidates are pinned and bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
