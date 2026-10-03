# Antigravity — rsi-autonomy-20260930

**Role:** Architecture, Operations & Verification Review
**Date:** 2026-09-30
**Status:** Read-only Expert Review

---

## 1. Architectural Diagnosis: The Validation Consumer Gap

Analysis of `scripts/automation/prsi-orchestrator.py`, `scripts/ai/lib/rsi_lifecycle.py`, and `config/runtime-prsi-policy.json` reveals the root cause of the autonomy disconnect:

1. **Dead-End State Sink (`rsi_awaiting_validation`)**:
   - `_run_rsi_delegate` (`prsi-orchestrator.py:893`) transitions successfully dispatched repairs to `rsi_awaiting_validation`.
   - The queue reconciliation loop (`_reconcile_rsi_queue:766-779`) only clears rows when the incident flips away from `"open"` in `.agent/collaboration/rsi-incidents.json`.
   - However, that status transition is governed by `rsi_lifecycle.resolve(incident_id, ...)` which has zero operational callers across systemd timers, automated services, or backend endpoints.

2. **Divergent Authority Gates**:
   - `require_independent_verifier_for_high_risk` requires `row.approval.verifier_by` via `prsi-orchestrator.py verify`.
   - `rsi_lifecycle.resolve()` enforces root cause, regression, and validation evidence strings without validating `verifier_by`.
   - As a result, execution and resolution operate under disjoint contracts with no unified bridge.

---

## 2. Minimal Plan for Closed-Loop Restoration

1. **Validator Consumer Service (`aq-rsi-validate`)**:
   - Implement an automated / scheduled validation driver that inspects `rsi_awaiting_validation` rows.
   - The validator executes test suites and diff checks against the target patch, verifies non-regression, and populates `approval.verifier_by` with the verifying lane identity.
   - Calls `rsi_lifecycle.resolve()` with concrete evidence strings extracted from the validation run.

2. **Stale Incident Hygiene & Triage**:
   - Stale open incidents in `.agent/collaboration/rsi-incidents.json` lacking verifiable repairs must be audited and either marked `resolved` with root-cause documentation or transitioned to `archived` / `wontfix`.
   - Do not allow unverified legacy incidents to trigger repetitive dispatch loops.

3. **Scoped Activation & Multi-Lane Dispatch**:
   - Generalize `prsi-orchestrator.py` `cmd_rsi_dispatch` to iterate through capability-ordered repair lanes (`["codex", "claude", "local"]`) rather than hardcoding a single lane.
   - Maintain strict dry-run guards until the validation consumer is active and proven.

---

## 3. End-to-End Acceptance Criteria

- **E2E Loop Verification**: Incident registered -> PRSI queue row ingested -> delegate executes repair -> validator consumer runs regression tests -> `verifier_by` set -> `rsi_lifecycle.resolve()` called -> queue row completed and archived.
- **Zero Orphaned States**: No queue rows indefinitely stalled in `rsi_awaiting_validation`.
- **Memory & Resource Bound**: Orchestrator and report processes operate strictly within their systemd cgroup `MemoryMax=256M` ceilings.

---

## 4. Verdict

**VERDICT:** `PLAN_READY_WITH_FOLLOWUPS`
