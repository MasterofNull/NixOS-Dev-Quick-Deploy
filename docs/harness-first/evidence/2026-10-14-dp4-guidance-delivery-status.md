# Evidence: DP-4 Truthful Guidance Delivery Status

## Context
Date: 2026-10-14
Slice: `fix/dp4-guidance-delivery-status`
Component: `assets/dashboard.js`, `dashboard/backend/api/routes/aistack.py`, `scripts/testing/test-pi-agent-streaming-ui.py`, `.agent/PROJECT-DP4-GUIDANCE-STATUS-PRD.md`
Author lane: codex (prior clearance session); independent reviewer: claude-sonnet (independent verifier)

## Problem
Root cause: the DP-4 guidance endpoint/UI reported guidance as delivered/injected even when it was only recorded or the spool write failed.

## Solution
Guidance is reported as recorded/pending (not delivered); persistence failure returns 503 and is explicit in the UI.

## Validation Evidence
- `python3 scripts/testing/test-pi-agent-streaming-ui.py`: `6/6 tests passed`.
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| codex (prior clearance session) | claude-sonnet (independent verifier) | PASS_WITH_FOLLOWUPS |

Review notes: Verified independently.

## Follow-ups
- Non-guidance control actions still say "Injected" (backlog OPEN, DP-4).

## Rule 15 Activation Attestation
- Integrated: YES - routes/aistack.py and dashboard.js are the live dashboard path.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: commit subject carries `DP-4` detection string in `.agents/plans/durable-proactive-mesh/tracker.json`; status projected.
