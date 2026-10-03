# Antigravity — tiered-auto-update-prd-r2-20261001

Note: Round r2 was superseded by collaborative round r3 (`tiered-auto-update-prd-r3-20261001`) following owner directives and consensus refreeze.

Full architectural recommendations, failure modes, and resource guards are recorded in `.agents/plans/tiered-auto-update-prd-r3-20261001/antigravity.md`.

Summary for r2:
1. Frontier vs Core: Frontier limited to approved agent CLIs and developer toolchains after build & consumer tests; Core covers host services and infrastructure.
2. Kernel: Staged build-only latest-stable per Owner Directive 2026-10-01; no unattended reboots.
3. Health Gate & Rollback: Exact closure deployment, 300s readiness window with 3 consecutive passes, instant rollback to previous closure.
4. Cadence & Guards: 15-minute zero-agent-activity lease, MemAvailable >= 8 GiB check, binary-cache requirement for heavy builds to protect resident llama.cpp.

VERDICT: PLAN_READY_WITH_FOLLOWUPS (superseded by r3)
