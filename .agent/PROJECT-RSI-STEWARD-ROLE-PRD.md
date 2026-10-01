---
title: RSI Steward Role PRD
status: DRAFT (design round open)
owner_directive: 2026-09-30
extends: .agent/PROJECT-RSI-READINESS-PRD.md
round: .agents/plans/rsi-steward-role-prd-20260930/
---

# RSI Steward — the recursive-self-improvement loop as a callable role

## Owner directive (2026-09-30)
Treat the RSI loop and workflow as a role/agent that (a) can be called and spun up
during routine work whenever friction, errors or issues arise, and (b) runs as a
timer-based health check that clears persistent system issues, warnings and errors
that nobody is actively working on but that degrade the system.

## Problem
- Self-healing is fragmented: six timers overlap (`ai-auto-remediate`,
  `ai-gap-auto-remediate`, `ai-stack-health-monitor`, `ai-prsi-orchestrator`,
  `ai-prsi-rsi-dispatch`, `disk-health-monitor`) with separate intakes, budgets and
  state; none owns "persistent degradation nobody is working on".
- RSI dispatch was silently inert for two days (verifier gate never proposed,
  skip reasons dropped) and then failed on three sandbox layers — nobody noticed
  because no role is accountable for the loop's own health.
- Friction found mid-task (hook denials, tool failures, flaky gates) is recorded
  (`rsi_lifecycle.failure`) but there is no way for a working agent to hand it off
  and keep going.

## Operating model (owner directive 2026-09-30, second clarification)
- The steward is a **domain sub-orchestrator** (spawnable sub-agent), not just a
  script: it owns the RSI domain end-to-end and runs its own team — intake/triage,
  diagnosis, implementer lanes (codex first, local later), validation — deciding and
  dispatching within its authority.
- **Higher-level orchestrators review the team's logic and work** (routing choices,
  repair patches, gate outcomes) asynchronously, as reviewers of the domain, not as
  per-step approvers.
- **Never gate on availability**: when a reviewer/perspective lane is unavailable, the
  steward proceeds and QUEUES the review/perspective/change for that lane's
  resume/catch-up (`.agent/collaboration/AGENT-CATCHUP-QUEUE.md`, Rule 18), so every
  agent's work eventually rolls into the system. Only owner-authority gates (high-risk
  verifier sign-off, activation, trunk protection) wait — and those are proposed
  CLI-first, never silently skipped.

## Goals (MVP)
1. **Role definition** `rsi-steward` in `docs/architecture/role-matrix.md` as a domain
   sub-orchestrator: authority = triage, diagnose, dispatch bounded repairs to lane
   implementers in isolated worktrees, validate, record; never self-approve high-risk
   rows, never commit to the shared checkout, never bypass verifier/budget gates.
   Reports up to the orchestrator; its decisions are reviewable after the fact.
   Lane-agnostic (Rule 18); executor lane per policy (`rsi.repair_lane`, codex
   first per remote-first proofing, local later).
2. **On-demand invocation**: one CLI `aq-rsi` (`report`, `status`, `pending`,
   `approve`) that any agent/user calls mid-task to hand off friction; it records
   via the existing `rsi_lifecycle.failure` identity/dedupe and returns
   immediately (non-blocking).
3. **Timer health sweep**: one steward sweep that collects persistent signals from
   existing producers (failed/degraded units, aq-qa phase-0 failures, health-spider
   alerts, code-scanning alerts, stale OPEN backlog items with a machine key) into
   the same ledger; recurring-but-unowned items are prioritized.
4. **Owner-in-the-loop, CLI-first**: high-risk repairs surface via
   `aq-resume` banner + `aq-rsi pending`; agent proposes exact approve command;
   dashboard is optional (owner preference 2026-09-30).
5. **Loop self-observability**: steward health = oldest pending age, executed vs
   skipped counts, stalled rows, per-lane success; alert when pending > 24h with
   executed = 0.

## Non-goals (MVP)
- Auto-merge or auto-commit to trunk; activation of new services without owner act.
- Replacing gates (verifier, budget, trunk protection).
- Tuning for local Qwen before the remote lane is proven.

## Consolidation question (decide in round)
Which existing timers fold into the steward sweep vs stay as signal producers
(recommendation: producers keep producing; only the steward decides/dispatches).

## Acceptance (MVP)
- A mid-task `aq-rsi report ...` from a Claude/Codex session creates/dedupes an
  incident and returns < 2s.
- The timer sweep ingests at least: failed systemd units, open code-scanning
  alerts, aq-qa phase-0 failures; re-running creates no duplicates.
- One real incident goes intake -> owner approve (CLI) -> codex repair in isolated
  worktree -> patch + validation evidence -> resolved, end-to-end.
- Steward health visible via CLI and alerting on stuck pending.

## Evidence / current state
Built 2026-09-30: code-scanning -> ledger bridge, aq-rsi-pending + aq-resume banner,
skip-reason persistence, dispatch unit sandbox fixes; lane switch in progress
(codex task codex-20260930-150253). See issues-backlog `rsi-dispatch-*` entries.

## Steward evidence log (rsi-steward, 2026-09-30)
- S1 `aq-rsi` CLI (`scripts/ai/aq-rsi`): `report` (rsi_lifecycle.failure; local, no model/network, <2s), `status` (steward health; missing queue = unknown, exit 2; alert on pending >24h with zero executed), `pending` (delegates to aq-rsi-pending), `approve` (prints the owner verify command only). Tests: `scripts/testing/test-aq-rsi.py`. `rsi_lifecycle` ledger paths accept `RSI_RUNTIME_DIR` / `RSI_BACKLOG_FILE` / `RSI_WORKAROUNDS_FILE` for isolated runs.
- S2 `aq-rsi sweep [--dry-run]` (`scripts/ai/lib/rsi_sweep.py`): observation-only ingest of failed units, code-scanning (existing intake planner; export older than 48h = unknown), aq-qa phase-0 failures (reads latest machine output, stale >6h or missing = unknown; never runs aq-qa) and aq-payload-audit high findings, via rsi_lifecycle identity/dedupe. No timers/units added (S5 is owner-activated). Tests: `scripts/testing/test-rsi-sweep.py`.
- S3 identity migration: intake now maps Trivy `note`/`warning`/`error` onto the ledger severity scale (an unmapped `note` aborted the intake mid-run). 21 code-scanning groups recorded under the new identity; 4 old-identity incidents (wheel, transformers, setuptools, jaraco.context) resolved as "identity migration"; GitPython old incident kept open (awaiting CI image rescan; `gitpython>=3.1.59` floor already in requirements.txt) and cross-annotated via `rsi_lifecycle.annotate`. Delegate degradation incidents recorded: local delegate success 0.47/24h and coordinator /stats/delegate 18% with all failures classified unknown.
- S4 floor policy: 87 exact `==` pins in ai-stack/mcp-servers/{aidb,hybrid-coordinator,nixos-docs,ralph-wiggum}/requirements.txt converted to `>=` floors; upper bounds kept (each commented) only for pytest-asyncio<1.0, llama-index-core<0.15, llama-index-embeddings-huggingface<0.7, openai<3, pandas<3. Guard: `scripts/testing/test-requirements-floor-policy.py` (no `==`, all lines parse; lock drift reported as WARN). requirements.lock files still predate several raised floors; refresh needs networked pip-compile (deferred).
- Tooling fix: `aq-integrity-scan` excluded references by absolute-path parts, so any checkout under `.agents/` (delegation worktrees) saw every file as an orphan and the commit-time logical-orphan guard failed with 400 false "new" orphans; it now checks repo-relative parts (regression in `test-aq-integrity-scan-contract.py`).
