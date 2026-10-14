# Evidence: DP-3 On-Call Daemon Review Revision

## Context
Date: 2026-10-14
Slice: `fix/dp3-oncall-review-revision`
Component: `scripts/ai/aq-oncalld`, `scripts/ai/lib/oncalld_engine.py`, `dashboard/backend/api/routes/aistack.py`, `scripts/testing/test-aq-oncalld.py`, `scripts/testing/harness_qa/phases/phase0.py`
Author lane: antigravity (original) + claude-sonnet (revision); independent reviewer: claude-sonnet (independent reviewer, 2 rounds)

## Problem
Root cause: PR #506 DP-3 daemon reported optimistic states, isolation could fail open, and shipped a fake ghp_ credential literal that tripped CI Secret Detection.

## Solution
Honest states, fail-closed isolation, reproducible bwrap confinement, dedup, offloaded git, daemon heartbeat, and no credential literals in source or tests.

## Validation Evidence
- `python3 scripts/testing/test-aq-oncalld.py`: `17/17 fixtures passed.` / `ALL 17 FIXTURES PASS`.
- Real bwrap confinement proven by reviewer: no network, read-only system, scrubbed credentials.
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| antigravity (original) + claude-sonnet (revision) | claude-sonnet (independent reviewer, 2 rounds) | PASS_WITH_FOLLOWUPS |

## Follow-ups
- Known limitations and follow-ups are recorded in backlog (DP-3 KNOWN-LIMITATION / OPEN).

## Rule 15 Activation Attestation
- Integrated: YES - dashboard route and aq-oncalld are the live path; pushed onto PR #506 branch.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; full real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: commit subject carries the `DP-3` detection string; status projected.
