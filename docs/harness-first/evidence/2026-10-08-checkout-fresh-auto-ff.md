# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-160

## Objective
- Every GitHub PR merge left the local checkout behind, and nrs preflight then failed ("checkout is N commit(s) behind origin/main"), forcing a manual pull every time. The guard now fast-forwards when git --ff-only can do so without touching local commits, uncommitted edits, or untracked files; otherwise it fails exactly as before. Opt-out: AUTO_FAST_FORWARD=0.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- The orchestrator made the edit directly: one guarded git call plus tests, reported as owner friction mid-session.

## Commands Executed
```bash
bash scripts/testing/test-check-checkout-fresh.sh   # 6/6 pass; new test 5 fails against the original guard
```

## Validation Evidence
- Test 2 (behind, with a conflicting uncommitted edit) gives exit 3 and the edit is preserved. Test 5 (clean, behind) gives a fast-forward to origin/main and exit 0. Test 6 (AUTO_FAST_FORWARD=0) gives exit 3 with HEAD unchanged.

## Rollback Plan
- Revert the commit, or set AUTO_FAST_FORWARD=0.

## Residual Risk
- A fast-forward could pull a commit that changes the guard or preflight itself mid-run. The rest of the preflight then runs the new code, which is the intended state of main anyway.

## Hint Feedback
- None.
