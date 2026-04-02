#!/usr/bin/env python3
"""Static checks for optional Phase 5 performance completions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPTIONS = ROOT / "nix" / "modules" / "core" / "options.nix"
MCP_SERVERS = ROOT / "nix" / "modules" / "services" / "mcp-servers.nix"
AI_STACK_ROLE = ROOT / "nix" / "modules" / "roles" / "ai-stack.nix"
CACHE_PREWARM = ROOT / "scripts" / "ai" / "aq-cache-prewarm"
DASHBOARD = ROOT / "dashboard.html"
ROADMAP = ROOT / ".agents" / "plans" / "PHASE-4-5-COMPLETION-ROADMAP-2026-03-30.md"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    options_text = OPTIONS.read_text(encoding="utf-8")
    mcp_text = MCP_SERVERS.read_text(encoding="utf-8")
    ai_stack_role_text = AI_STACK_ROLE.read_text(encoding="utf-8")
    cache_prewarm_text = CACHE_PREWARM.read_text(encoding="utf-8")
    dashboard_text = DASHBOARD.read_text(encoding="utf-8")
    roadmap_text = ROADMAP.read_text(encoding="utf-8")

    assert_true(
        "startupWarmEnable = lib.mkOption" in options_text,
        "cache prewarm options should expose startup warm enable toggle",
    )
    assert_true(
        "startupQueries = lib.mkOption" in options_text,
        "cache prewarm options should expose declarative startup warm queries",
    )
    assert_true(
        "AI_SEMANTIC_CACHE_WARM_ON_START=" in mcp_text,
        "hybrid coordinator service should inject semantic cache warm-on-start env",
    )
    assert_true(
        'AI_SEMANTIC_CACHE_WARM_QUERIES=${lib.escapeShellArg (lib.concatStringsSep "|" ai.aiHarness.runtime.cachePrewarm.startupQueries)}' in mcp_text,
        "hybrid coordinator service should shell-escape semantic cache startup queries so systemd preserves spaced prompts",
    )
    assert_true(
        'scripts/ai/aq-cache-prewarm' in ai_stack_role_text and 'AI_CACHE_PREWARM_QUERY_COUNT=' in ai_stack_role_text,
        "periodic cache prewarm service should invoke the bounded cache prewarm wrapper with an explicit broad-seed fallback count",
    )
    assert_true(
        '--from-report "${REPORT_PATH}"' in cache_prewarm_text and 'run_fallback' in cache_prewarm_text,
        "aq-cache-prewarm should prefer report-driven rag prewarm and fall back to broad routing seeds",
    )
    assert_true(
        'data-card-id="deployment-ops"' in dashboard_text,
        "deployment operations section should participate in dashboard lazy loading",
    )
    assert_true(
        "lazyLoadManager.registerCard('deployment-ops', 'loadDeploymentOps');" in dashboard_text,
        "deployment operations should register with the lazy-load manager",
    )
    assert_true(
        "loadDeploymentOps();" not in dashboard_text.split("document.addEventListener('DOMContentLoaded', () => {", 2)[1].split("connectMetricsWebSocket();", 1)[0],
        "deployment operations should not load eagerly during initial dashboard boot",
    )
    assert_true(
        "2. [x] Add semantic cache warm-up on service start" in roadmap_text,
        "Phase 5 completion roadmap should mark semantic startup warm-up complete",
    )
    assert_true(
        "2. [x] Lazy dashboard data loading" in roadmap_text,
        "Phase 5 completion roadmap should mark lazy dashboard loading complete",
    )

    print("PASS: optional Phase 5 performance tasks are wired and tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
