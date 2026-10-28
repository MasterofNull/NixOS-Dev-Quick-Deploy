# Codex lean review prompts and review-reserved budget (2026-10-27)

## Source
Plan item P1.5 of `.agents/plans/system-integrity-recovery`. Headless Codex review logs from 2026-10-27
(`.agents/delegation/outputs/codex-20261027-*.log`, "tokens used" lines).

## Defect
- Four headless Codex reviews cost 99346, 66706, 63619 and 46664 tokens (total 276335 against the 250000
  daily budget). Each fresh session explored the repo to find the diff.
- `daily_budget_check()` summed logs by local calendar date in the filename against one budget shared by all
  roles, so about 3-4 reviews exhausted it and a review could not run once implement runs had used it.

## Fix
- `scripts/ai/aq-review-request`: resolves PR head, embeds a size-capped diff (default 40000 bytes, stat added
  and truncation noted) in a read-only prompt with an output contract (`Reviewed-head-sha`, file:line findings,
  `Review-Disposition`), then dispatches to the codex (`--role review --effort medium --mode safe`) or local lane.
- `scripts/ai/delegate-to-codex`: budget is a rolling window by log mtime
  (`DELEGATE_CODEX_BUDGET_WINDOW_HOURS`, default 24); `DELEGATE_CODEX_REVIEW_RESERVE_PCT` (default 40)
  keeps part of the budget for `--role *review*`; refusals print when headroom frees;
  `--budget-check-only --role R` reports used/total, implement and review headroom, window, next free time.
  The quota cooldown check and `--force-budget` are unchanged.

## Evidence
- `scripts/testing/test-delegate-headless-budget.py` (window ignores old logs; review allowed while implement
  refused; both refused at total; force-budget; next-free time) and `scripts/testing/test-aq-review-request.py`
  (stubbed git/gh/dispatchers: prompt content, truncation, codex/local argv) pass.
- Both registered in `config/ci-checks.json`; `check-ci-manifest-coverage.sh` passes.
- Dry-run on PR 638 and live `--budget-check-only` output are in the slice report.

## Known gap
- Token counts come from the "tokens used" log line; a run that never writes it counts as 0.
- Lean prompts reduce but do not cap exploration; the reviewer is instructed, not sandboxed, to stay within the diff.
- The budget is a soft guard; `quota_cooldown_active` remains the primary real-quota guard.
- Callers (review funnel docs) are not yet switched to `aq-review-request`.

## Shared delegation dir

Every delegate script derived its delegation dir from its own location (`$SCRIPT_DIR/../..`), so a script copy running inside a git worktree under `.agents/delegation/worktrees/<name>` used that worktree's own `registry.jsonl`, `outputs/` and budget logs. `delegate-to-codex --budget-check-only` from a worktree reported 0/250000 while the shared outputs held 276335 tokens (a budget bypass), and worktree-dispatched tasks were invisible to the main registry and to `aq-review-receipt`. The delegation dir is now resolved from the repository's main worktree (`git rev-parse --path-format=absolute --git-common-dir`, parent + `/.agents/delegation`) via `scripts/ai/lib/delegation-dir.sh` (bash) and `scripts/ai/lib/delegation_dir.py` (python), used by `delegate-to-{codex,local,claude,gemini,antigravity}`, `delegate-fanout`, `aq-review-request` and `aq-review-receipt` (registry default; output files fall back to the main root). `AQ_DELEGATION_DIR` still overrides; if git is unavailable the old script-relative path is used with one stderr warning. Regression test: `scripts/testing/test-delegation-dir-resolution.py` (fails against the old behavior with 0/250000, passes now). Post-fix, `delegate-to-codex --budget-check-only --role review` from the worktree reports 276335/250000.
