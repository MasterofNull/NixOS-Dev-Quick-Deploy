# Evidence: Role-Route Fail-Closed Lane Exclusion

## Context
Date: 2026-10-14
Slice: `fix/role-route-exclusion-fail-open`
Component: `scripts/ai/aq-role-route`, `scripts/testing/test-agent-agnostic-router.py`
Author lane: claude (fix); defect origin antigravity (#496); independent reviewer: claude-sonnet (independent reviewer, 2 rounds)

## Problem
Root cause: Lane exclusion in aq-role-route failed open (#496): task-run, sub-agent and alias-prefixed tokens were not matched, so the self-review ban could be bypassed.

## Solution
Exclusion now matches those token forms exactly for the excluded lane and an empty candidate set fails closed.

## Validation Evidence
- `python3 scripts/testing/test-agent-agnostic-router.py`: `PASS: all agent-agnostic router checks`.
- `test-lane-eligibility.py`: `PASS: all lane-eligibility checks`; `test-agent-executor-role-eligibility.py`: `6/6 tests passed`; `test-agent-dispatch-contract.py`: `OK`.
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude (fix); defect origin antigravity (#496) | claude-sonnet (independent reviewer, 2 rounds) | PASS |

## Follow-ups
- None.

## Rule 15 Activation Attestation
- Integrated: YES - aq-role-route is the live dispatch router.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; full real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: no tracked plan item; no status hand-set.
