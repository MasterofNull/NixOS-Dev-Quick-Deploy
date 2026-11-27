# PRSI dispatch path unit wedged in unit-start-limit-hit (2026-11-26)

## Objective

`ai-prsi-rsi-dispatch.path` (PathChanged=/var/lib/nixos-ai-stack/rsi/rsi-incidents.json) has been `failed` with `unit-start-limit-hit` since 2026-11-25 12:06 PST. Find the cause, fix the producer where it is ours, and stop a write burst from wedging the path.

Finding: the premise that the dispatch sync rewrites the watched ledger is not what the code does. `cmd_sync` (scripts/automation/prsi-orchestrator.py, `_sync_locked`) writes the PRSI action queue (`optimizer/prsi/action-queue.json`) via `_save_queue`, not `rsi-incidents.json`; it only reads the incident ledger. The ledger is rewritten by other producers: `rsi_lifecycle.failure()` (scripts/ai/lib/rsi_lifecycle.py ~102-160) increments `count` and sets `last_seen` on every re-observation, then `_save()` replaces the file. Live ledger today shows health-spider incidents with counts 1092, 737, 153, 123 and the file mtime advancing every ~25 s (10:32:16, 10:35:05, 10:35:30, 10:35:53) while the dispatch service was not running. Each write fires PathChanged; bunched writes (journal 11:50:56 twice 0.4 s apart, 11:50:59) start the oneshot faster than the default StartLimitBurst=5 / 10 s and systemd marks the path failed.

Separate real defect found on the way: `updated: 50` in every sync event. `_sync_locked` bumped `last_seen_at`/`seen_count` and rewrote `action-queue.json` for every re-observed row even when `confidence`, `reason`, `raw_action`, `estimated_token_cost` were identical. That rewrite is not watched, but it is pointless I/O and made `seen_count` count sync runs.

## Workflow/Session IDs

Headless bug-fix slice, worktree `agent-a139fc150c8d3085d`, branch `worktree-agent-a139fc150c8d3085d`. No tier0, no commit (files staged for the orchestrator).

## Delegation Decision

Implemented directly by the delegated slice agent (bounded, single concern). No further sub-agents.

## Commands Executed

- `journalctl -u ai-prsi-rsi-dispatch.service --since '2026-11-25 11:50'` - runs of ~250 ms, `executed: 0`, `updated: 50`, spaced 0.4-27 s apart.
- `stat` on the live ledger three times, 20 s apart - mtime advanced with the dispatch service idle.
- Python read of the ledger: most recently seen incidents are all `health-spider` producers with counts 123-1092.
- `python3 scripts/testing/test-prsi-sync-idempotent.py` and the neighbouring prsi tests (below).
- `nix-instantiate --parse nix/modules/roles/ai-stack.nix`.

Changes:
1. scripts/automation/prsi-orchestrator.py `_sync_locked`: an existing row whose meaningful fields are unchanged is skipped (no `last_seen_at`/`seen_count` bump, not counted in `updated`); `_save_queue` runs only when the serialized queue differs from what was loaded. Atomic tmp+rename in `prsi_queue.save` is untouched.
2. nix/modules/roles/ai-stack.nix: `ai-prsi-rsi-dispatch.path` now watches `${mutableRsiDir}/rsi-incidents.new` instead of the ledger. scripts/ai/lib/rsi_lifecycle.py `failure()` atomically rewrites that marker (`{"id","ts"}`, tmp+rename) only when an incident id is newly inserted or re-opened from a non-open status; count/last_seen re-observations never touch it, and `count` semantics are unchanged. The marker lives in the existing tmpfiles-declared `mutableRsiDir` that every ledger writer already has write access to (Rule 13/14). The 5-minute timer stays as the lost-event backstop. `rsi_lifecycle.failure` is the only writer that inserts new incidents (rsi_sweep goes through it).
3. scripts/testing/test-prsi-sync-idempotent.py (new), registered in config/ci-checks.json next to test-prsi-rsi-intake.py (both lists; check-ci-test-coverage passes).

Why not a systemd debounce: an earlier version used . Review (Gemini) showed it holds the unit in stop-post about 80% of the time (ledger rewritten every ~25 s), delays stop/shutdown up to 60 s, and PathChanged triggers do not queue during deactivation as claimed. It was removed. TriggerLimit*/StartLimit* only drop or fail the path, or remove the protection. Fixing the trigger source (marker) removes the burst itself.

Not changed on purpose: `rsi_lifecycle.failure()` still bumps `count`/`last_seen` on every call. `rsi_convene.trigger_for` uses `count` for the repeat trigger and test-rsi-lifecycle asserts count == 24 for 24 calls, so a throttle there is a semantic change that needs its own decision (see Residual Risk).

## Validation Evidence

- test-prsi-sync-idempotent.py: PASS idle sync (two extra runs) leaves queue bytes and mtime unchanged with `added=0 updated=0`; PASS new incident writes; PASS changed incident updates row and bumps `seen_count` to 2.
- test-prsi-rsi-intake, test-prsi-queue-single-writer, test-prsi-queue-fail-closed, test-prsi-queue-path-ssot, test-prsi-budget-reservation, test-coordinator-prsi-canonical-queue: all PASS.
- check-cross-surface-contract.py: PASS. tier0.d/check-ci-test-coverage.sh: PASS (722 declared, 92 exempt).
- nix-instantiate --parse: ok. ruff on the new test: clean (two pre-existing findings in prsi-orchestrator.py lines 189 and 512, untouched). basedpyright on the new test: clean.
- Staleness misjudgment found and fixed: the first version of the sync change stopped advancing `last_seen_at` for unchanged rows, so a still-present rejected alert_human row would have looked 14 days stale to aq-prsi-review and been cleared. Fix: refresh `last_seen_at` for unchanged rows when it is at least 1 day old (no `seen_count` bump, not counted in `updated`). The test covers a January `last_seen_at` being refreshed and the next sync leaving the file unchanged. test-rsi-lifecycle.py (14 tests) also passes.
- Marker tests: test-rsi-lifecycle.py (15 tests) asserts a re-observation leaves the marker bytes and mtime unchanged while a new or re-opened incident rewrites it. test-prsi-sync-idempotent.py now uses a relative 2-day-old sentinel instead of a hardcoded date. `cmd_rsi_dispatch`'s `_save_queue` is guarded by the same serialized-diff check as sync.
- Not verified live: the Nix change needs a rebuild; behaviour after deploy is unobserved.

## Rollback Plan

Revert the three files (orchestrator edit, ai-stack.nix hunk, test + ci-checks entry). To re-arm the path without a deploy, which is also needed after deploy because the unit stays failed until reset:

```
sudo systemctl reset-failed ai-prsi-rsi-dispatch.path && sudo systemctl start ai-prsi-rsi-dispatch.path
```

## Residual Risk

- Until the Nix change is deployed and the path is reset, the path stays failed; the 5-minute timer still runs the dispatch.
- The ledger is still rewritten every ~25 s by health-spider re-observations (`rsi_lifecycle.failure` count/last_seen churn); it no longer triggers dispatch. Coalescing those writes would change `count` semantics and is a separate owner decision.
- Incidents opened by a writer that bypasses `rsi_lifecycle.failure` would not touch the marker and wait for the 5-minute timer.
- `seen_count` now counts real changes, not sync runs; it is display-only in aq-prsi-review. Its staleness check (alert_human rows, 14-day window) reads `last_seen_at`, which is now refreshed at most once per day for unchanged rows, so staleness is accurate to within a day.

## Hint Feedback

No aq-hints query was run (headless slice). The task premise (sync rewrites the watched ledger) was wrong; journal and ledger mtime evidence located the real writer. Hints for this area should point to `rsi_lifecycle.failure` as the ledger writer and `prsi_queue.save` as the queue writer.
