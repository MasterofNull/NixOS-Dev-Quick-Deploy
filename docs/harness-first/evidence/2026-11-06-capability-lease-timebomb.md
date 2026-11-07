## Objective
Remove wall-clock time bombs from the capability-lease tests before the golden parent's 2026-12-31 expiry. From 2027-01-01 three assertions would have failed.

## Workflow/Session IDs
Branch fix/capability-lease-timebomb, worktree `.agents/delegation/worktrees/lease-bomb`. Date 2026-11-06.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet 5.5 (Rule 17, bounded edits in two test files plus this evidence doc).

## Commands Executed
- Run each test normally, then under libfaketime (`LD_PRELOAD=<libfaketime.so.1> FAKETIME="@2027-03-01 12:00:00" FAKETIME_DONT_RESET=1`, library fetched via `aq-tool libfaketime`) at 2027-03-01 and 2031-01-01. The preload is inherited by the CLI and checker subprocesses.
- `scripts/testing/test-capability-lease.py`:
  - CLI verify case now writes a lease derived from golden `valid`, re-signed with the DEV key and expiring now+1h, and runs the real `aq-lease verify` on it.
  - Added a CLI case verifying the golden 2020 `expired` lease, expecting `expired` and a non-zero exit.
  - `fresh_child` is built from a parent re-minted at now+2h, with the child expiring at now+1h.
  - Two further wall-clock calls found by the faketime run (`is_expired(golden["valid"])`, the epoch-stale `verify`) pinned to `GOLDEN_NOW`.
- `scripts/testing/test-asymmetric-lease-authority.py`: legacy `verify()` calls on the 2026-12-31 fixture pinned to `now=2026-08-07`.
- `scripts/testing/test-state-authorities.py`: no change; its 2026-12-31 values are fixture data evaluated against the pinned `FIXED_DATE`.
- No production change: `aq-lease` and `capability_lease.py` are untouched, and no clock flag or env var was added. Golden byte-parity assertions are unchanged.

## Validation Evidence
Root cause: golden leases carry absolute expiries but several `verify()`/`is_expired()` calls and the CLI subprocess used the real clock.

Results (normal, 2027-03-01, 2031-01-01):
- test-capability-lease.py: `56 passed, 0 failed (of 56 assertions)` in all three runs. Before the fix, 2027-03-01 gave `FAIL: epoch-stale: verify() with stale current_epoch -> epoch-stale` once the CLI and fresh_child cases were fixed.
- `PASS: dev-key: CLI verify of freshly-minted (golden-derived) lease -> ok` and `PASS: dev-key: CLI verify of golden 'expired' lease -> expired (rejected)` in all three runs.
- test-asymmetric-lease-authority.py: `24 passed, 0 failed` and `PASS: asymmetric lease authority crypto valid` in all three runs.
- test-state-authorities.py: `PASS: 27 state-authority checks` in all three runs, so it is not date-sensitive.

## Rollback Plan
Revert the two test files and this evidence file. No data or config migration.

## Residual Risk
- Tier0 and the CI wrapper were not run (out of scope for this slice).
- The faketime check covers these three tests only; other tests with wall-clock dependence were not swept.
- The asymmetric test's `verify_authoritative` does not check expiry; that is existing behavior, not changed here.
