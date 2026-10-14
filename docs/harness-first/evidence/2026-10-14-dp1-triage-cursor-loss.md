# Evidence: DP-1 Triage Cursor Stops at First Rate-Limited Entry

## Context
Date: 2026-10-14
Slice: `fix/dp1-triage-cursor-loss-v2`
Component: `scripts/ai/lib/triage_engine.py`, `scripts/testing/test-aq-triage.py`
Author lane: codex (port of 8c070b6e); independent reviewer: claude-sonnet

## Problem
Root cause: the triage cursor advanced past entries that were rate-limited (not processed), so those entries were permanently skipped (lost) on the next run.

## Solution
The cursor now stops at the first rate-limited entry, so deferred entries are re-evaluated on the next run (lossless). A regression test covers the cursor behaviour.

## Validation Evidence
- `python3 scripts/testing/test-aq-triage.py`: `Ran 7 tests ... OK`, `ALL 6 FIXTURES PASS`.
- tier0 `--pre-commit`: see PR body / commit record.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| codex | claude-sonnet (independent porting reviewer) | PASS_WITH_FOLLOWUPS |

## Follow-ups
- One throttled source delays later sources (backlog OPEN, DP-1 triage).

## Rule 15 Activation Attestation
- Integrated: YES - `triage_engine.py` is on the live `aq-triage` path.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: unit/fixture tests above; real-world run DEFERRED (2026-10-14) pending activation.
- Observable: DEFERRED (2026-10-14): no new metric; existing triage logs unchanged.
- Intervenable: existing aq-triage CLI; no new control surface needed.
- PM-tracked: commit subject carries `DP-1` detection string for `.agents/plans/durable-proactive-mesh/tracker.json`; status projected.
