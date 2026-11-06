## Objective
Tests cannot mutate live state. The test gate fails if `git status` changes after a test group runs. Slice P0.6 of system-integrity-recovery.

## Workflow/Session IDs
Slice P0.6 (system-integrity-recovery). Branch fix/tests-no-live-state. Measurement and report: `.agents/delegation/outputs/p06-test-isolation/REPORT.md` and the `measure-*.json` files in that directory.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17). Date: 2026-11-04.

## Commands Executed
- Measured each test in 6 throwaway repo copies, with the same env as `scripts/testing/run-test-group.py`, a 60 s cap, and a `git status` delta per test (`measure.py`, `run-measure.sh`).
- Re-measured the mutating tests after the fixes (`measure-after-*.json`).
- Ran `verify.sh`: test groups tests-aqos, tests-context, and tests-dashboard, plus both former mutators under `run_one`.

## Validation Evidence
Mutating tests before the fix: 2. Both are `test_exempt` scripts. No group test changed the tree.

| test | paths changed | root cause |
|---|---|---|
| `scripts/testing/test-aq-loop-review-repair-guard.py` | `.agent/collaboration/rsi-incidents.json`, `.agent/memory/issues-backlog.md` | `scripts/ai/lib/rsi_lifecycle.py` resolves the ledger and backlog to the checkout unless `RSI_RUNTIME_DIR` or `RSI_BACKLOG_FILE` is set. The runner did not set them. |
| `scripts/testing/test-dashboard-advanced-runtime-summary.py` | `.agent/oncall/oncall.db`, `.agent/triage/triage_state.sqlite` | `aistack.py` builds the on-call and triage engines under the checkout. The hooks `AQ_ONCALL_STATE_DIR` and `AQ_TRIAGE_STATE_DIR` existed, but the runner did not set them. Also, `triage_engine.health_summary(repo_root)` ignored `AQ_TRIAGE_STATE_DIR` when a caller passed `repo_root`. The dashboard always does. |

Fixes:
1. `scripts/testing/run-test-group.py` sets the state-path env vars in each test's temp dir: `RSI_RUNTIME_DIR`, `RSI_BACKLOG_FILE`, `PRSI_INCIDENTS_FILE`, `AQ_ONCALL_STATE_DIR`, `AQ_TRIAGE_STATE_DIR`, `PULSE_LOG_PATH`, `RESUME_JSON_PATH`. These hooks already existed.
2. `scripts/ai/lib/triage_engine.py` `health_summary` honors `AQ_TRIAGE_STATE_DIR`. The default is unchanged.
3. `scripts/testing/run-test-group.py` gate. It snapshots `git status --porcelain --untracked-files=all` and content hashes of the listed files before and after the group. It exits 1 and names the changed files.
4. Regression test `scripts/testing/test-run-test-group-state-isolation.py`. It builds a temp git repo with a deliberately mutating dummy test and asserts rc=1 and the file name. A clean test must pass. It is registered in `config/ci-checks.json` under `tests-misc-n-r`.

After the fix:
- Mutating tests before: 2 (`measure-before-1.json`, `measure-before-5.json`).
- Mutating tests after: `measure-after-0.json` still lists one mutator, the dashboard test, with `.agent/triage/triage_state.sqlite` changed. The other five `measure-after-*.json` files are empty.
- The report says fix 2 addresses that mutator. It also says `verify.sh` passed with clean git status: tests-aqos 12/12, tests-context 14/14, tests-dashboard 22/22. Both former mutators ran under `run_one` with clean git status. The report gives a count after of 0.
- The `measure-after-0.json` result predates a clean re-measure. No JSON in the directory records a zero count. The zero comes from the `verify.sh` run in the report.

## Rollback Plan
Revert the changes to these four files: `scripts/testing/run-test-group.py`, `scripts/ai/lib/triage_engine.py`, `scripts/testing/test-run-test-group-state-isolation.py`, and `config/ci-checks.json`. No data or config migration is involved.

## Residual Risk
- Exempt tests are not run by `run-test-group`. No group lists them, so the gate does not cover them. They are clean only when run with the `run_one` env. The open PR `feat/ci-all-test-files` changes exemptions. It should route them through the runner.
- The gate works per group (4 parallel workers). It names changed files, not the test that changed them.
- The measurement used a 60 s per-test cap. The runner allows 120 s. Tests that hit 60 s were not fully measured.
- A full after-run of every group through the runner was not repeated. Per-test re-measure and 3 groups were re-run.
- The owner checkout has an untracked `.agent/oncall/`. It holds stale output from earlier runs. It was not touched. Per Rule 12, the owner archives it.

## Hint Feedback
None recorded in the source report.
