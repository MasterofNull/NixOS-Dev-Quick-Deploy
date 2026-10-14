# Evidence: DP-2 Durable Intent Legal Transitions and Fail-Closed Claims

## Context
Date: 2026-10-14
Slice: `audit/gemini-codex-clearance-20261014`
Component: `scripts/ai/lib/durable_runtime.py`, `scripts/ai/aq-durable`, `dashboard/backend/api/routes/aistack.py`, `scripts/testing/test-aq-durable.py`, clearance PRD/memory/ACTIVATION-AUDIT/WORKAROUND-REGISTER/backlog
Author lane: codex (prior clearance session) + claude-sonnet (reconcile-loop fix); independent reviewer: claude-sonnet (independent reviewer)

## Problem
Root cause: DP-2 durable runtime allowed illegal intent state transitions, non-fail-closed claims, and reconcile re-ran in-flight intents (double-exec risk); pre-repair code fails fixtures 5-8.

## Solution
Legal-transition enforcement, fail-closed claims, reconcile skips in-flight intents and continues; clearance PRD and memory/audit records included.

## Validation Evidence
- `python3 scripts/testing/test-aq-durable.py`: `10/10 fixtures passed. ALL 10 FIXTURES PASS`.
- tier0 `--pre-commit`: 0 failed (see commit/PR).

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| codex (prior clearance session) + claude-sonnet (reconcile-loop fix) | claude-sonnet (independent reviewer) | PASS_WITH_FOLLOWUPS |

Review notes: No double-exec path found.

## Follow-ups
- Stuck EXECUTING/RECONCILING intents without a lease (backlog DEFERRED, DP-2).

## Rule 15 Activation Attestation
- Integrated: YES - durable_runtime.py is the live aq-durable/dashboard path.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: commit subject carries `DP-2` detection string in `.agents/plans/durable-proactive-mesh/tracker.json`; status projected.
