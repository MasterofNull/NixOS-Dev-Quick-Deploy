# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-130

## Objective
- Fix three defects from the first two live runs of the Antigravity implementer lane (#461). Those runs
  validated the lane end-to-end on the real IDE: new worktree window, claim via absolute paths, edits only
  in the worktree, commit on the `delegate/` branch, and completion in about 3–4 minutes.
  1. **False main-checkout drift.** Task `antigravity-20261010-165325-4enn5v` was rejected as drift. The
     agent never touched the main checkout. The orchestrator had unstaged runtime ledgers (`M ` → ` M`)
     after an autostash conflict, and the fingerprint hashed porcelain status codes. Runtime ledgers
     (`rsi-incidents.json`, `AGENT-CATCHUP-QUEUE.md`) are also rewritten at any time. Fix: the fingerprint
     is now the set of modified tracked paths, with status codes ignored and those ledgers excluded. The
     HEAD fast-forward rule is unchanged.
  2. **Duplicate wakes.** The dispatcher (`auto-delegate`) and the path-unit auto-wake (`owner-manual`)
     woke the same task 7 ms apart. That is two `--new-window` calls, so two IDE windows, and the existing
     60s debounce lost the race. Fix: a per-task `fcntl.flock` on `receipts/<tid>.wake.lock` around the
     whole wake. A successful wake within `AQ_ANTIGRAVITY_WAKE_DEDUPE_S` (default 120) is recorded as
     `skipped-recent-wake`.
  3. **Stale briefs.** The first task's premise had already been fixed on main by another lane (d120b60d),
     between brief-writing and dispatch. The agent faithfully changed already-correct defaults, so the
     result was NOT merged. Fix: the implementer contract now starts with "check origin/main first; if
     present write `ALREADY PRESENT: <evidence>` and complete without changes". A no-change completion
     carrying that marker is accepted as outcome `already-present`; a no-change completion without it is
     still rejected.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f
- Live tasks: antigravity-20261010-165325-4enn5v (stale premise, not merged),
  antigravity-20261010-170154-am6w3f (accepted, PR feat/precommit-main-checkout-guard-20261010)

## Delegation Decision
- Sonnet implementer. Antigravity did not implement these fixes, because they change the completion gate
  that guards Antigravity's own work and the reviewer must be independent. The orchestrator diagnosed all
  three defects from live receipts and the main-checkout state, and reviewed the diff.

## Commands Executed
```bash
python3 scripts/testing/test-antigravity-implementer-lane.py
python3 scripts/testing/test-antigravity-inbox.py
python3 scripts/testing/test-delegate-to-antigravity.py
python3 scripts/testing/test-antigravity-claim-receipt.py
python3 scripts/testing/test-lane-hook-parity.py
python3 scripts/testing/test-subagent-workflows-antigravity.py
```

## Validation Evidence
- `test-antigravity-implementer-lane.py` PASS. New cases cover:
  - Staging churn on an already-modified file, and ledger rewrites: accepted. A newly modified other tracked
    file: rejected.
  - Two wakes in the window produce one `--new-window`, and the second records `skipped-recent-wake`. With
    the window set to 0, a wake opens again. Three concurrent wakes produce one window.
  - The contract contains `ALREADY PRESENT:`. With the marker and no changes, the completion is accepted
    as `already-present`; without the marker, it is rejected.
- The inbox, delegate, claim-receipt, lane-hook-parity and subagent-workflows suites pass.
  `test-antigravity-inbox.py` has one assertion updated: a deduped wake now records `skipped-recent-wake`
  instead of nothing.

## Rollback Plan
- Revert the PR commit.

## Residual Risk
- If an agent edits a file that was already modified in the main checkout before dispatch, the drift check
  does not detect it (documented limitation, unchanged).
- Whether the live agent follows the "check origin/main first" step will be shown by its next live tasks.

## Hint Feedback
- None.
