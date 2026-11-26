# S1-LEDGER: durable work ledger library and CLI

## Objective

Slice S1 (`s1-ledger`) core of `.agents/plans/agent-work-durability-20261119/DESIGN.md`, including Revision 1 (F5, F15, F17) and Revision 3 (torn records): an append-only `<dispatch-id>.jsonl` ledger per dispatch, reduced on read, with one Python writer under `flock`, and the `aq-ledger` CLI.

## Workflow/Session IDs

- Implementer: Claude Sonnet 5.5, headless delegate, branch `feat/s1-work-ledger`, worktree `.agents/delegation/worktrees/feat-s1-work-ledger`. Orchestrator session id not supplied.

## Delegation Decision

Bounded five-file slice assigned by the orchestrator, plus a round 2 brief adding `config/activation-manifest.json` and `.gitignore`. No further delegation. Changes left uncommitted for independent review.

## Commands Executed

- `python3 -m py_compile scripts/ai/lib/work_ledger.py scripts/ai/aq-ledger scripts/testing/test-work-ledger.py`
- `ruff check` and `basedpyright` on the same three files
- `python3 scripts/testing/test-work-ledger.py`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`
- `bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh`
- `python3 scripts/testing/test-aq-usage-logging.py`
- `python3 scripts/testing/run-test-group.py tests-aq`, then selected tests again through its `run_one`
- `aq-ledger` smoke run against a temp delegation dir, and a read-only `aq-ledger check` against the real delegation dir

## Validation Evidence

Round 2 (activation registration). Added to the slice: `config/activation-manifest.json` (deferred entry for `scripts/ai/aq-ledger`, `health_signal` `scripts/ai/aq-ledger:_run`) and `.gitignore` (`.agents/delegation/ledger/`). This fixes the `tier0` failure `new entrypoint scripts/ai/aq-ledger has no entry in config/activation-manifest.json`. Run with both files staged; only the full tier0 gate was not rerun here.

```text
$ python3 -m json.tool config/activation-manifest.json > /dev/null
rc=0
$ git check-ignore -v .agents/delegation/ledger/test.jsonl
.gitignore:235:.agents/delegation/ledger/	.agents/delegation/ledger/test.jsonl
rc=0
$ bash scripts/governance/tier0.d/check-activation-manifest.sh
[activation-manifest] deferred: aq-oncalld autonomous on-call incident daemon (2026-10-28)
[activation-manifest] deferred: operator guidance spool (aq-human-intervention control queue) (2026-10-28)
[activation-manifest] deferred: durable runtime (idempotent effect ledger, aq-durable) (2026-10-28)
[activation-manifest] deferred: RSI convene expert rounds (Codex, Gemini, local design-only seats) (2026-11-06)
[activation-manifest] deferred: durable work ledger CLI (aq-ledger, S1 core) (2026-11-26)
[activation-manifest] 8 entries, 0 fail, 0 warn
rc=0
```

Round 1 required commands, final run, verbatim:

```text
$ python3 -m py_compile ...
rc=0
$ ruff check ...
All checks passed!
rc=0
$ basedpyright ...
0 errors, 0 warnings, 0 notes
rc=0
$ python3 scripts/testing/test-work-ledger.py
test_check_corrupt (__main__.CliTest.test_check_corrupt) ... ok
test_check_empty (__main__.CliTest.test_check_empty) ... ok
test_check_stale (__main__.CliTest.test_check_stale) ... ok
test_end_to_end (__main__.CliTest.test_end_to_end) ... ok
test_errors (__main__.CliTest.test_errors) ... ok
test_executable (__main__.CliTest.test_executable) ... ok
test_global_delegation_dir_flag (__main__.CliTest.test_global_delegation_dir_flag) ... ok
test_concurrent_appends (__main__.ConcurrencyTest.test_concurrent_appends) ... ok
test_default_dir_without_git (__main__.LifecycleTest.test_default_dir_without_git) ... ok
test_env_delegation_dir_is_default (__main__.LifecycleTest.test_env_delegation_dir_is_default) ... ok
test_full_lifecycle (__main__.LifecycleTest.test_full_lifecycle) ... ok
test_invalid_ids_rejected (__main__.LifecycleTest.test_invalid_ids_rejected) ... ok
test_modes (__main__.LifecycleTest.test_modes) ... ok
test_overrides_and_missing_pid (__main__.LifecycleTest.test_overrides_and_missing_pid) ... ok
test_record_envelope_and_single_line (__main__.LifecycleTest.test_record_envelope_and_single_line) ... ok
test_symlinked_entry_refused (__main__.LifecycleTest.test_symlinked_entry_refused) ... ok
test_writer_refusals (__main__.LifecycleTest.test_writer_refusals) ... ok
test_invalid_window_rejected (__main__.ProjectionTest.test_invalid_window_rejected) ... ok
test_last_event_boot_id_decides (__main__.ProjectionTest.test_last_event_boot_id_decides) ... ok
test_prior_boot_leaves_other_states (__main__.ProjectionTest.test_prior_boot_leaves_other_states) ... ok
test_prior_boot_running_is_interrupted (__main__.ProjectionTest.test_prior_boot_running_is_interrupted) ... ok
test_stale_window (__main__.ProjectionTest.test_stale_window) ... ok
test_append_after_torn_tail_stays_clean (__main__.TornAndCorruptTest.test_append_after_torn_tail_stays_clean) ... ok
test_complete_final_line_with_bad_schema_fails_closed (__main__.TornAndCorruptTest.test_complete_final_line_with_bad_schema_fails_closed) ... ok
test_mid_file_corruption_fails_closed (__main__.TornAndCorruptTest.test_mid_file_corruption_fails_closed) ... ok
test_missing_or_foreign_init_fails_closed (__main__.TornAndCorruptTest.test_missing_or_foreign_init_fails_closed) ... ok
test_terminated_garbage_final_line_is_torn (__main__.TornAndCorruptTest.test_terminated_garbage_final_line_is_torn) ... ok
test_torn_init_needs_attention_and_can_be_reinitialised (__main__.TornAndCorruptTest.test_torn_init_needs_attention_and_can_be_reinitialised) ... ok
test_torn_tail_preserves_done_steps (__main__.TornAndCorruptTest.test_torn_tail_preserves_done_steps) ... ok

----------------------------------------------------------------------
Ran 29 tests in 3.350s

OK
rc=0
$ bash scripts/governance/tier0.d/check-ci-test-coverage.sh
[tier0.d/check-ci-test-coverage] PASS (814 tests: 722 declared, 92 exempt)
rc=0
```

Smoke run (temp delegation dir, then the real one):

```text
smoke-1  running  claude  implementer  -  smoke
aq-ledger check: PASS (1 entries, 0 need attention)
rc=0
aq-ledger check: PASS (0 entries, 0 need attention)
rc=0
```

`tests-aq` group: `run-test-group tests-aq: 82/88 passed`. The six failures:

- `test-aq-router.sh`: caused by this run's own shell exporting `AQ_USAGE_TELEMETRY=0`. Rerun without it: rc=0.
- `test-aq-land.py`: `timeout after 120s` in the parallel group. Rerun alone: rc=0, 16 tests in 95.638s.
- `test-approval-recovery.py`, `test-approval-signer.py`, `test-aq-approve-headless.py`: `ModuleNotFoundError: No module named 'fido2'` in this shell.
- `test-approval-runbook-engine.py`: 8 cases report `unauthorized`. Not diagnosed. This slice does not touch the approval code; no baseline run on `origin/main` was made.

Found during validation and fixed: the new CLI lacked the `aq-usage-hook` that `test-aq-usage-logging.py` requires of every `aq-*` entrypoint; the standard hook then needed a `pyright: ignore` to keep basedpyright clean.

### Behavior decided beyond the brief

- Before appending, the writer moves a torn final line to `<id>.jsonl.torn` (0600, fsynced) and truncates it off. Without this, the next append (for example reconcile writing `interrupted`) would merge with or bury the fragment and turn a tolerated torn tail into mid-file corruption.
- A complete, valid-JSON final line that fails schema validation fails closed; only an unterminated or undecodable final line counts as torn.
- `auto_resume_allowed` is true only for `resume_policy: auto` with status `queued`, `checkpointed` or `interrupted`.
- `resume_policy` defaults to `confirm`.
- `last_heartbeat` is the time of the latest valid event of any type.
- The reduced view also carries `status_reason` and `interrupted_reason`.

## Rollback Plan

Revert the commit. Nothing calls the library or CLI yet. A `ledger/` directory created by manual use can be archived (Rule 12).

## Residual Risk

- Not activated (Rule 15 deferral, 2026-11-26): no wrapper writes entries and no tier0 check runs `aq-ledger check`. The tracker's validation goal for `s1-ledger` is "schema test + wrappers write entries", so this slice meets only the first half. A commit subject containing `S1-LEDGER ` would match the tracker's detection rule.
- The activation deferral is registered in `config/activation-manifest.json`; S1b (wrapper writes and the tier0 ledger check, immediately after S5 merges) closes it.
- Through the CLI, `pid` and `pid_start_ticks` describe the short-lived `aq-ledger` process, not the worker. The wrapper wiring slice needs a `--pid` flag before using them for liveness.
- `brief_path` is stored as given; the "under `.agents/delegation/`" rule is not enforced here (S5).
- A torn final record is lost by design. If it was a terminal `status`, an `auto` entry can project as resumable, so S3 must check ground truth before acting.
- A reader can briefly report `needs-attention` for an entry whose `init` has created the file but not yet written it.
- A corrupt entry stays `needs-attention` until its file is archived.
- Power-loss durability relies on `fsync` semantics and was not tested with a real crash; torn writes are simulated.

## Hint Feedback

None. Headless delegate; `aq-hints` was not queried. Round 2 touched `config/activation-manifest.json`, `.gitignore` and this file; its `check-activation-manifest` PASS output is under Validation Evidence.
