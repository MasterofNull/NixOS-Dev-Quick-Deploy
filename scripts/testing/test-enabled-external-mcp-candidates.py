#!/usr/bin/env python3
"""Validate enabled external MCP candidates stay pinned and bounded."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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


def assert_semgrep_config(entry: dict) -> None:
    args = entry.get("args") or []
    joined = " ".join(args)
    assert entry.get("command") == "nix", "Semgrep MCP must run through Nix"
    assert args[:4] == ["shell", "nixpkgs#uv", "-c", "uvx"], "Semgrep MCP must use Nix-provided uvx"
    assert "semgrep-mcp==0.9.0" in args, "Semgrep MCP must be pinned"
    assert "semgrep-mcp" not in args, "Semgrep MCP must not use an unpinned package"
    assert "semgrep-mcp@latest" not in joined, "Semgrep MCP must not use latest"
    assert "--transport" in args and "stdio" in args, "Semgrep MCP must use stdio transport"
    assert "SEMGREP_APP_TOKEN" not in (entry.get("env") or {}), "Semgrep cloud token must not be configured"


def assert_enabled_candidate(entry: dict, pinned_version: str) -> None:
    assert entry["state"] == "enabled"
    assert entry["pinned_version"] == pinned_version
    assert entry["review_status"] == "accepted-with-mitigations"
    assert entry.get("mitigations"), f"{entry['id']} must document mitigations"


def main() -> int:
    claude = load_json(".claude/settings.json")
    gemini = load_json(".gemini/settings.json")
    continue_cfg = load_json("ai-stack/continue/config.json")
    registry = load_json("config/agent-capability-intake-candidates.json")

    assert_playwright_config(claude["mcpServers"]["playwright"])
    assert_playwright_config(gemini["mcpServers"]["Playwright MCP"])
    cont_pw = next(item for item in continue_cfg["mcpServers"] if item["name"] == "Playwright MCP")
    assert_playwright_config(cont_pw)
    assert_semgrep_config(claude["mcpServers"]["semgrep"])
    assert_semgrep_config(gemini["mcpServers"]["Semgrep MCP"])
    cont_semgrep = next(item for item in continue_cfg["mcpServers"] if item["name"] == "Semgrep MCP")
    assert_semgrep_config(cont_semgrep)

    candidates = {item["id"]: item for item in registry["candidates"]}
    assert_enabled_candidate(candidates["playwright-mcp"], "0.0.76")
    assert "@playwright/mcp@0.0.76" in candidates["playwright-mcp"]["install"]["args"]
    assert candidates["github-mcp-readonly"]["state"] == "blocked-auth-runtime", "GitHub MCP requires valid auth and runtime before enablement"
    assert_enabled_candidate(candidates["semgrep-mcp"], "0.9.0")
    assert "semgrep-mcp==0.9.0" in candidates["semgrep-mcp"]["install"]["args"]
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
    assert candidates["osv-scanner"]["state"] == "pending-rebuild"
    assert candidates["osv-scanner"]["pinned_version"] == "2.2.4"
    assert candidates["osv-scanner"]["review_status"] == "accepted-with-mitigations"
    assert candidates["syft-grype"]["state"] == "pending-rebuild"
    assert candidates["syft-grype"]["pinned_version"] == "syft-1.38.0+grype-0.104.1"
    assert candidates["syft-grype"]["review_status"] == "accepted-with-mitigations"
    assert candidates["code-intelligence-graph-layer"]["state"] == "blocked-graph-incomplete"

    print("PASS: enabled external MCP candidates are pinned and bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
