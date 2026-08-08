#!/usr/bin/env python3
"""Hermetic H0 contract checks for the proposed Herdr capability intake."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config/agent-capability-intake-candidates.json"
PRD = ROOT / ".agent/PROJECT-HERDR-AGENT-OPERATIONS-PRD.md"
PROGRAM = ROOT / ".agents/plans/herdr-agent-operations/PROGRAM-PLAN.md"
REPORT = ROOT / ".agents/plans/herdr-agent-operations/H0-INTAKE-REPORT.md"


def need(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def text(path: Path) -> str:
    need(path.is_file(), f"missing required H0 artifact: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


registry = json.loads(text(REGISTRY))
entries = registry.get("candidates", [])
candidate = next((item for item in entries if item.get("id") == "herdr-agent-multiplexer"), None)
need(isinstance(candidate, dict), "Herdr candidate registry entry is required")
need(candidate.get("state") == "proposed", "H0 candidate must remain proposed")
install = candidate.get("install", {})
need(install.get("type") == "disabled-external-repo", "H0 install must be disabled external repo")
need(install.get("command") == "disabled-until-intake", "H0 install command must remain disabled")
permissions = candidate.get("permissions", {})
need(permissions.get("network") is False and permissions.get("writes") is False and permissions.get("secrets") is False, "H0 grants no network/write/secret permissions")
need(permissions.get("filesystem") == "none", "H0 grants no filesystem permission")
need(candidate.get("tool_allowlist") == [], "H0 grants no tools")
notes = candidate.get("activation_notes", "")
for forbidden in ("No download", "install", "socket access", "plugin", "session restore", "process launch", "remote attach", "agent skill"):
    need(forbidden in notes, f"registry activation notes must prohibit {forbidden}")

prd = text(PRD)
program = text(PROGRAM)
report = text(REPORT)
for corpus_name, corpus in (("PRD", prd), ("program", program), ("report", report)):
    need("Herdr" in corpus, f"{corpus_name} must identify Herdr")
need("presentation" in prd.lower() and "not the task registry" in prd.lower(), "PRD must keep Herdr presentation-only")
need("PREPARED_ONLY" in report, "H0 report must be prepared-only")
need("v0.7.5" in report and "Apache-2.0" in report and "Nix" in report, "report must bind release, license, and Nix feasibility")

prohibitions = ("direct socket", "plugin", "integration", "agent skill", "session restore", "remote attach", "herdr update", "manifest")
lower_report = report.lower()
for item in prohibitions:
    need(item in lower_report, f"report must prohibit or mitigate {item}")
need("no active cmux runtime integration" in lower_report, "report must not claim active cmux runtime")

tabs = ("control", "reasoning", "implementation", "review", "research", "local", "ops")
for tab in tabs:
    need(f"`{tab}`" in report, f"missing deterministic tab {tab}")
need("seven-tab" in lower_report, "report must declare deterministic seven-tab layout")
for boundary in ("no download", "no runtime capability", "no install", "no socket"):
    need(boundary in lower_report, f"report must preserve H0 boundary: {boundary}")
need("provider change" in lower_report and "routing change" in lower_report, "report must prohibit provider/routing changes")

print("PASS: Herdr H0 intake contract")
