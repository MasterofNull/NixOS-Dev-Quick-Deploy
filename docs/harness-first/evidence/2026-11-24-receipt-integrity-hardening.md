# PR #826 receipt integrity hardening

Follow-up for `PR826-RESIDUAL-HARDENING` from `codex-20261122-222447-6lfwgf`.

## Findings and fixes

1. Registry completion hashed output using an unbounded read under the registry lock. `TaskRegistry._output_stamp` now uses the bounded regular-file reader with a 16 MiB cap. It skips symlinks, non-regular files, oversized files, and files detected changing during the read. The reader opens with `O_NONBLOCK` so a FIFO swapped in between `lstat` and `open` cannot stall it.
2. A local receipt passed to pre-merge verification could describe a different PR or reviewed head. `aq-land` now supplies `--pr` and `--head` for local receipt verification alongside `--require-revocation-check`. `aq-review-receipt verify` validates these arguments and checks both bindings against the same parsed receipt used for integrity verification.
3. Publishing a revocation did not refresh an existing `review-disposition` result. After publication succeeds, `aq-review-receipt revoke` checks whether the PR is open at the revoked head. It requests one rerun per distinct workflow run ID from matching check URLs. Lookup and rerun failures emit stderr notes and preserve the successful revocation exit status. `--no-rerun` skips the GitHub lookup and rerun. `AQ_REVIEW_RECEIPT_GH` selects the executable, with `gh` as the default.

## Round 2

- For a merge-only PR whose current head differs from the revoked head, `_maybe_rerun_open_pr_check` also matches the last `Reviewed-head-sha:` line in the open PR body after normalizing line endings.
- `_read_bounded_regular_file` loops over bounded `os.read` calls to assemble short reads and still rejects files over the byte limit.
- `verify` and `revoke` require a positive integer when `--pr` is supplied. Local receipt verification rejects a JSON boolean `pr` when binding to `--pr 1`.

## Verification

```sh
python3 -m py_compile scripts/ai/lib/task_registry.py scripts/ai/aq-review-receipt scripts/ai/aq-land scripts/testing/test-aq-review-receipt.py scripts/testing/test-aq-land.py
basedpyright scripts/ai/lib/task_registry.py scripts/ai/aq-review-receipt scripts/ai/aq-land scripts/testing/test-aq-review-receipt.py scripts/testing/test-aq-land.py
ruff check scripts/ai/lib/task_registry.py scripts/ai/aq-review-receipt scripts/ai/aq-land scripts/testing/test-aq-review-receipt.py scripts/testing/test-aq-land.py
export TMPDIR=.
python3 scripts/testing/test-aq-review-receipt.py
TMPDIR=. python3 scripts/testing/test-aq-land.py
```

- `py_compile` passed.
- Basedpyright exited 1 with 49 errors and zero warnings. Comparison against `60c58b377` found zero new diagnostics.
- Ruff exited 1 with eight diagnostics. Comparison against `60c58b377` found the same seven `B904` and one `B905` diagnostics, with zero new diagnostics.
- The receipt suite passed all 39 tests. Round 2 regression cases cover nonpositive PR numbers, boolean PR binding, one-byte reads at the output stamp limit, and the merge-only PR body match with two stubbed workflow reruns.
- The landing suite passed all 108 tests across eight shards. Its pre-merge regression checks the exact local receipt verification arguments and confirms that failed verification prevents merge.

## Rule 15 activation attestation

The changes are integrated into registry stamping, receipt verification and revocation, and the landing merge check. The default paths are enabled in the changed code. End-to-end verification in this slice covered local Git publication and the CLI interaction with stubbed GitHub responses. The published revocation record and stderr messages expose the result. Operators can skip reruns with `--no-rerun`.

Deferred on 2026-11-24 to integration review for PR #826. Deployed activation, an authenticated GitHub rerun, and live PM tracker attestation remain pending.

## Rollback

Use `aq-review-receipt revoke --no-rerun` with the usual revocation arguments to stop rerun requests while continuing to publish revocations. For a full rollback after integration, revert the slice through the normal reviewed delivery workflow. Preserve the published revocation records.
