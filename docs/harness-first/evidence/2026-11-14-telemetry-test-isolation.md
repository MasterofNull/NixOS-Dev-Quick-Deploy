# Tests can no longer write live delegation telemetry

Date: 2026-11-14
Task ID: HF-20261114-S4b

## Objective
- F3 MVP slice S4b (Rule 19 root-cause fix). The live `.agents/delegation/outcome-receipts.jsonl` held one row, "PR 77", and `power-gate-deferred.jsonl` (mode 0644) held a `fixture` task row. This traces the producer, fixes it, and archives the fixture rows.
- Delivered: `test-aq-land.py` now sets `AQ_DELEGATION_DIR` to a temp dir and asserts the receipt lands there (0600); `power_gate.py --defer-log` creates its file 0600; fixture rows copied to the archive with cleaned replacements (orchestrator applies the `mv`).

## Workflow/Session IDs
- Workflow ID: none (bounded slice from `.agents/delegation/outputs/resume-20261114/F3-MVP-FREEZE-DRAFT-rev2.md` section 2a)
- Session ID: Simurg@claude/sonnet; orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Delegated by the orchestrator to a Sonnet 5.5 implementer (Rule 17). Review is by a separate lane; the implementer does not self-review or merge.

## Commands Executed
```bash
# producer trace: which test opens the live files (strace -f -e trace=openat, per test)
strace -f -e trace=openat -o st.txt python3 scripts/testing/test-aq-land.py
rg 'delegation/(outcome-receipts|power-gate)' st.txt     # live outcome-receipts.jsonl opened (O_RDONLY) by aq-land's record_landing
# before/after of the live files across test-aq-land, test-aq-land-outcome, test-outcome-receipt, test-local-power-gate
sha256sum .agents/delegation/{outcome-receipts,power-gate-deferred}.jsonl
python3 scripts/testing/test-aq-land.py
python3 scripts/testing/test-local-power-gate.py
```

## Validation Evidence
- Producer of the PR 77 row: `scripts/testing/test-aq-land.py`. Its stub `gh` returns `n = 77` for `pr create` (line ~116); the test env set `AQ_LAND_STATE_DIR` etc. but not `AQ_DELEGATION_DIR`, so `aq-land record_outcome` calls `resolve_delegation_dir(HERE)`, which resolves through the git common dir to the live `.agents/delegation`. strace shows the live `outcome-receipts.jsonl` opened by the aq-land subprocesses. Since `record_landing` dedupes by PR number, the first run wrote the row (head `681db447...`, 2026-11-13 19:06 local) and every later run returns "duplicate", so the live file stays byte-identical and the leak is invisible to a before/after hash.
- Before/after on the live files (size mtime sha256 prefix): receipts 349 / 1794625588 / 8979cd97305cd93c, deferred 213 / 1794625780 / 731a24a88fceb6dd, identical across test-aq-land, test-aq-land-outcome, test-outcome-receipt, test-local-power-gate (the dedupe masks aq-land, as above).
- The `fixture` defer row: not reproduced. strace of `test-local-power-gate.py` and of 17 other tests that call `delegate-to-local` shows none opening `power-gate*` in the live dir (they only read the live `registry.jsonl`). The row has real sensor readings and was written 2026-11-13 19:09:40, while the committed power-gate test arrived in #776 at 21:26, so it came from a pre-isolation iteration of the S3 development, not from a current test. Status: cause inferred, not reproduced.
- Fix 1: `test-aq-land.py` env gets `AQ_DELEGATION_DIR=<tmp>/deleg`; `test_happy_path_no_clutter_commit` asserts the receipt (PR 77, mode 0600) is in that dir. Without the env var that assertion fails, which is the regression guard.
- Fix 2: `power_gate.py` opens the defer log with `os.open(..., 0o600)`; `test_cli_defer_exit_and_log` asserts mode 0600.
- Test results and gate output are pasted in the commit hand-off report.

## Rollback Plan
- `git revert <sha>`. Trigger: test-aq-land or test-local-power-gate failing for reasons tied to the env var or file mode.
- Live files: originals are at `.agent/archive/20261114-telemetry-fixtures/*.orig`; restore with `cp -p`.

## Residual Risk
- Other tests that run `delegate-to-local` without `AQ_DELEGATION_DIR` (about 17 of them) only read the live registry today; a future gate-DEFER path in them would write to the live defer log. Not changed here (one slice, one concern).
- The `fixture` row's exact producer is unproven.
- The dedupe-by-PR behaviour hides repeated leaks; the new assertion in test-aq-land catches the unset env var directly.

## Hint Feedback
- No aq-hints used; the producer was found by strace of the candidate tests.
