# aq-land hardening evidence

`PR845-CLOSURE-OPERAND-FLAG-MATCH` requires two non-flag operands in the upstream closure comparison evidence. Options recognized by the comparison pattern can still precede the operands. The regression tests exercise five flag-only or one-operand comparisons and three valid two-operand comparisons.

`AQ-LAND-MERGE-IN-PROGRESS-RACE` handles GitHub's “Merge already in progress” response by polling the PR's state and exact head. The recovery succeeds only if the expected head reaches `MERGED`. It stops on a changed head, a terminal state other than `MERGED`, or an `OPEN` PR at the deadline. Other merge errors stop immediately. A merge command that exits successfully still requires `MERGED` on the expected head.

`AQ_LAND_MERGE_POLL_TIMEOUT_S` defaults to 60 seconds. The existing checks deadline caps the recovery window, and the polling interval is at most two seconds. A value of `0` allows the first state check and stops immediately if the PR is still `OPEN`.

## Verification

```sh
python3 -m py_compile scripts/ai/aq-land scripts/testing/test-aq-land.py
basedpyright scripts/ai/aq-land scripts/testing/test-aq-land.py
ruff check scripts/ai/aq-land scripts/testing/test-aq-land.py
TMPDIR=. python3 scripts/testing/test-aq-land.py
```

Compilation exited `0` with no output. On baseline `142559777` and on the candidate, basedpyright exited `1` with `18 errors, 0 warnings, 0 notes` and Ruff exited `1` with `Found 6 errors.` The diagnostics matched after normalizing source coordinates. Both comparisons found zero new diagnostics.

The test command exited `0` with 114 tests across eight shards. Each shard printed `OK`. The summaries below are in completion order.

```text
Ran 14 tests in 78.867s
Ran 14 tests in 104.395s
Ran 14 tests in 106.502s
Ran 15 tests in 115.247s
Ran 14 tests in 117.680s
Ran 14 tests in 118.259s
Ran 14 tests in 122.977s
Ran 15 tests in 154.483s
```

## Rule 15 activation attestation

- **Integrated and enabled by default.** Both fixes run through the regular `aq-land` evidence check and merge path in the candidate. Merge recovery uses the default timeout without additional configuration.
- **Validated end to end in the test environment.** The suite exercises the executable with isolated Git repositories and a GitHub CLI stub. It verifies that matching-head recovery clears `expected_checks`, logs `merged=True`, and appends an outcome receipt. It also covers the fail-closed paths.
- **Observable and intervenable.** The CLI reports when recovery starts and why it stops. Freshness logs and outcome receipts record successful merges. Operators can bound recovery with `AQ_LAND_MERGE_POLL_TIMEOUT_S` and rerun `aq-land` to resume after a timeout.
- **Deferred on 2026-11-24.** Deployment, live GitHub validation, and live PM tracking remain with the orchestrator after review and landing.

## Rollback

Revert the eventual slice commit through the normal PR workflow to restore the previous evidence parser and merge behavior. The change needs no state or receipt migration. The reverted CLI ignores `AQ_LAND_MERGE_POLL_TIMEOUT_S`.
