# Self-awareness guards: fails-without-the-fix, cited claims, wasted-work metrics

## Objective

Owner-approved 2026-11-27: turn three lessons from 2026-11-25/26 into enforced practice. (1) A bug fix or new gate/test must show the test failing against pre-fix code. (2) Capability/limit/performance/enforcement claims must cite the probe that shows them. (3) Wasted work becomes visible in aq-baseline: duplicate reviews per head, aq-land reruns, land-queue age, guard deny rate.

## Workflow/Session IDs

- Implementer: Claude Sonnet 5.5 sub-agent (headless, worktree agent-ac7f41ca44a0c4a3e). Orchestrator session id not supplied.

## Delegation Decision

Bounded multi-file slice (one criteria file, one aq-land line, one canon block, four baseline rows with tests) routed to a Claude Sonnet implementer by the orchestrator. Changes are staged, not committed.

## Commands Executed

- `python3 scripts/testing/test-aq-baseline.py`, `python3 scripts/testing/test-aq-land.py`
- `python3 scripts/governance/canon-compile.py --write` then `--check`
- `python3 scripts/testing/test-instruction-budget.py`, `test-aq-canon-compiler.py`
- `python3 scripts/governance/check-cross-surface-contract.py`
- `ruff check`, `basedpyright` on `aq_baseline.py`
- Pre-change replay: the new baseline tests run against `git show HEAD:scripts/ai/lib/aq_baseline.py`

## Validation Evidence

Criteria: new `config/review-criteria/default.md` (correctness; fails-without-the-fix; claims cite measurements). `aq-land` `Land.prompt` now always prepends it, before the dependency-bump and `--criteria-file` text, so it reaches every reviewer prompt (local and remote lanes). The old fallback sentence is item 1 of the file. New test `test_default_criteria_reach_every_reviewer_prompt` (normal, non-fast-lane path) asserts both criteria appear in the gemini prompt and the dependency-bump text does not. `test-aq-land.py`: Ran 16 tests, OK (133 s).

Implementer rule: `canon/blocks/headless-delegate-mode.md` gained two sub-agent bullets (fails-without-the-fix; claims cite measurements). `canon-compile.py --write` updated only `.agent/WORKFLOW-CANON.md` (the one full-text target); the summary file and LOCAL-AGENT.md are untouched. `canon-compile.py --check`: OK, no canon drift. `test-instruction-budget.py`: Ran 2 tests, OK. `test-aq-canon-compiler.py`: 13 tests OK. `check-cross-surface-contract.py`: PASS, no runtime/module/service changes. `ruff`: all checks passed. `basedpyright aq_baseline.py`: 0 errors, 0 warnings.

Baseline rows (`scripts/ai/lib/aq_baseline.py`), all `improves_when=down`, `unit_label=aggregate`, each reports `no_producer` when its input is absent and never a zero:
- `duplicate_reviews_per_head` (windowed): registry runs with role review/reviewer; head parsed from the aq-land brief text (`head <40-hex>`); value = runs beyond the first per (head, lane); runs with no parseable head count as `unknown_n`. A registry with no review runs is a measured 0.
- `aq_land_reruns` (windowed): failure-events kinds `checks_infra_runner_lost` / `checks_runner_rerun_failed`; `no_producer` until one is emitted (same AT-3 rule as `receipt_mint_failures`).
- `land_queue_oldest_age_s` (current-only): oldest entry age from `outputs/aq-land-queue/state.json`; empty queue is 0; a file that is a JSON list rather than an object of item states is `no_data`.
- `guard_deny_rate` (windowed): deny count over decided rows in `.agents/telemetry/bash-tool-policy.jsonl`; undecidable rows are `unknown_n`. There are no labels, so this is an upper bound on the false-deny rate, stated in the row's `eligibility_filter`.

Rule 1 applied to our own tests. Run against the pre-change `aq_baseline.py` (`git show HEAD:...`), all five new tests fail:

```
FAIL test_wasted_work_rows_no_producer_never_zero KeyError 'aq_land_reruns'
FAIL test_duplicate_reviews_per_head_counts_excess_runs_per_lane KeyError 'duplicate_reviews_per_head'
FAIL test_aq_land_reruns_counts_both_kinds_in_window KeyError 'aq_land_reruns'
FAIL test_land_queue_age_oldest_entry_and_empty_queue KeyError 'land_queue_oldest_age_s'
FAIL test_guard_deny_rate_is_deny_share_with_unknown_reported KeyError 'guard_deny_rate'
```

Against the patched file: `test-aq-baseline.py` prints `PASS: test-aq-baseline` (all tests ok). Replay of the two new aq-land tests against the pre-change tool (`git show 622941289^:scripts/ai/aq-land` copied over `scripts/ai/aq-land`, then `unittest` on `DepFastLane.test_default_criteria_reach_every_reviewer_prompt` and `DepFastLane.test_missing_default_criteria_file_warns_and_falls_back`): both FAIL (`'Fails-without-the-fix' not found in 'Independent review ...'`; `'WARN default review criteria unreadable' not found`). The patched tool was restored afterwards (`cmp` identical).

Producer schemas, read from the writers in their worktrees (not yet on main): (a) bash policy log: `scripts/ai/aq-bash-tool-policy-hook` `_log` (lines 22-32) writes `{"ts": <epoch float>, "decision": "allow"|"deny", "rule", "token"}` to `AQ_BASH_POLICY_LOG` or `<project>/.agents/telemetry/bash-tool-policy.jsonl`; the parser reads exactly `ts` (numeric epoch) and `decision`, and a decision other than allow/deny is `unknown_n`. (b) queue state: `scripts/ai/aq-land-queue` `read_state`/`write_state`/`set_state` (lines 86-105) store `{item_name: {state, reason, updated: ISO-Z, ...}}` in `state.json` under `AQ_LAND_QUEUE_DIR` or `<delegation>/outputs/aq-land-queue` (line 52); states queued/committing/landing/landed/failed/retry_wait (line 16). The producer records no enqueue time (`cmd_add`, lines 268-284, writes none), so the row measures seconds since the last state change of the oldest unfinished item (queued/committing/landing/retry_wait), and an item added but not yet transitioned has no state entry, so it is not seen. (c) rerun kinds: `scripts/ai/aq-land` `record_failure` call sites at lines 1017-1047 use exactly `checks_infra_runner_lost` and `checks_runner_rerun_failed`; rows go to `outputs/aq-land/failure-events.jsonl` (line 1193) with `at` and `kind`, matching the existing parser. Fixtures use these exact shapes.

## Review r2 Fixes (Gemini REQUEST_CHANGES)

- `duplicate_reviews_per_head` membership/n covered only duplicate runs, so a clean 20+ window rendered `insufficient`, and an all-unreadable window reported 0: membership and n are now the runs with a readable head; value is None when every run is unreadable. Test `test_duplicate_reviews_clean_window_is_descriptive_and_unreadable_is_unknown` fails on the old code.
- The row ignored `cohort=lane=<agent>`: now filtered by lane like the other registry rows. Test `test_duplicate_reviews_honours_lane_cohort` fails on the old code.
- `Fixture.env()` now pins `AQ_LAND_QUEUE_DIR` and `AQ_BASH_POLICY_LOG`; test `test_fixture_env_ignores_callers_queue_and_policy_paths` fails without the pins.
- The fails-without-the-fix replay for the aq-land tests was run against the pre-change tool (above); the queue-file wording was inverted and is corrected.

## Rollback Plan

Revert the commit. `aq-land` also tolerates a missing `default.md`: it prints `WARN default review criteria unreadable` and uses the previous one-line criterion (test `test_missing_default_criteria_file_warns_and_falls_back`).

## Residual Risk

Criteria are advisory prompt text: a reviewer lane can ignore them; enforcement is the reviewer's finding, not a mechanical gate. Baseline rows for queue age, reruns and guard deny rate stay `no_producer` until their producers exist; their input schemas come from unmerged producer worktrees (see above) and must be re-checked when those merge. The duplicate-review head is parsed from brief text, so a changed brief wording moves runs to `unknown_n` rather than miscounting.

## Hint Feedback

None.
