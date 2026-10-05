# Antigravity — rsi-steward-role-prd-20260930

**Role:** Architect / PRD Review
**Date:** 2026-09-30
**Status:** Read-only Expert Review

---

1. Boundary and Authority:
   - The steward role boundary is correct: it serves as a unified triage and scheduling coordinator, never an unconstrained self-approving repair runner.
   - Patch preparation in an isolated worktree is strictly segregated from live integration/activation; owner CLI approval remains mandatory for non-trivial and system-level actions.
   - Producing a passing patch transitions state to `repair_ready`; transitioning to `resolved` requires post-application verification and regression pass.
2. Timer & Service Consolidation:
   - Retain as Telemetry Producers: `ai-stack-health-monitor` (aq-qa observer) and `disk-health-monitor` (privileged hardware observer). They produce evidence without execution authority.
   - Fold into Steward Sweep: `ai-auto-remediate` (15m remediation loop) and `ai-gap-auto-remediate` (Ralph/aider triggers), centralizing incident scheduling under one engine.
   - Retire: Ad-hoc independent auto-remediation triggers once the unified steward sweep is validated.
3. Minimal Shippable MVP Slices (<=5 slices):
   - S1: Core CLI & Ledger (`aq-rsi status/report/pending` over canonical state dir; <2s response, deduplicated intake).
   - S2: Observation-Only Sweep (ingest unit failures, phase0 results, code-scanning; non-zero exits flag unknown rather than silently passing).
   - S3: Approval & Budget Leasing (CLI approval binding, atomic worktree leases, daily token/time ceilings).
   - S4: Single E2E Proof (one approved repair executed in an isolated git worktree with verified test evidence).
   - S5: Service Cutover (unify timers, preserve active queues across restart, register aq-qa integration gate).
4. Failure Modes & Controls:
   - Runaway Repairs: Enforce per-incident retry ceiling (max 3), mandatory cooldowns, and a kill-switch environment variable.
   - Duplicate Incidents: Incident identity must hash stable attributes (service name, test identifier, error class) rather than transient timestamps or worktree paths.
   - Sandboxing: Isolate worktree builds from shared repo HEAD; forbid unreviewed direct commits to main.
5. What to Cut from MVP:
   - Cut autonomous service restarts, dashboard approve/execute endpoints, free-text backlog ingestion, and secondary monitoring spiders.

VERDICT: PLAN_READY_WITH_FOLLOWUPS (Freeze exact resource ceilings and require live post-switch verification for `resolved`)
