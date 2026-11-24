# aq-land failure telemetry

Date: 2026-11-24

- Failed Tier0 runs now increment the checkpoint counter on both the staged-commit and pre-committed branch paths. After a successful retry, the outcome receipt includes the earlier failure.
- Tier0 failures, negative review verdicts, exhausted reviewer lanes, failed CI checks, and timed-out CI checks append structured events to `outputs/aq-land/failure-events.jsonl` under the resolved delegation directory. The journal is created with mode `0600`. An append error emits a warning and preserves the landing stop.
- Duplicate check names retain the worst state in the rollup. The ranking is `pass` (0), `pending` (1), `fail` (2). The later entry wins ties, so a later success cannot replace the run ID or state of a pending or failed check.
- `gh_poll()` recognizes GitHub's GraphQL 5xx message `Something went wrong while executing your query` and retries it with the existing backoff and deadline.

## Failure event schema

Each append writes one sorted-key JSON object followed by a newline.

| Fields | Values |
| --- | --- |
| `schema`, `at` | Schema version `1` and an ISO 8601 UTC timestamp |
| `stage`, `kind` | `tier0` / `tier0_failed`, `review` / `review_negative` or `review_exhausted`, `checks` / `ci_checks_failed` or `ci_checks_timeout` |
| `branch`, `pr`, `head_sha`, `author_lane` | Branch name, explicit or checkpoint PR number (null before a PR is known), head SHA, and author lane |
| `lane`, `run_id` | Reviewer lane and review run ID when available |
| `checks` | Array of objects with `name`, `run_id`, and `status` (`fail` or `pending`). A run ID is empty when GitHub has supplied none. |
| `detail`, `log_path` | Up to 240 characters of metadata, plus the saved log path when available |

Unset scalar metadata uses an empty string except for `pr`. Events contain an exit code for Tier0, a verdict or lane availability notes for review, or check names for CI. Raw stdout, stderr, and secrets stay out of the journal. The Tier0 event points to the existing blocker log for full output.

## Verification

| Command | Clean `c2160cc1f` | Working tree |
| --- | --- | --- |
| `python3 -m py_compile scripts/ai/aq-land scripts/testing/test-aq-land.py` | | Exit 0, no output |
| `basedpyright scripts/ai/aq-land scripts/testing/test-aq-land.py` | `18 errors, 0 warnings, 0 notes` (exit 1) | `18 errors, 0 warnings, 0 notes` (exit 1) |
| `ruff check scripts/ai/aq-land scripts/testing/test-aq-land.py` | `Found 6 errors.` (exit 1) | `Found 6 errors.` (exit 1) |

Diagnostic text matches the baseline after removing source coordinates. The delta is zero for both tools.

`TMPDIR=. python3 scripts/testing/test-aq-land.py` exited 0. All eight shards reported `OK`, with 118 tests total. The shard summaries in completion order were:

```text
Ran 15 tests in 53.898s
Ran 14 tests in 64.605s
Ran 14 tests in 70.602s
Ran 15 tests in 72.607s
Ran 15 tests in 81.322s
Ran 15 tests in 85.746s
Ran 15 tests in 88.670s
Ran 15 tests in 116.182s
```

## Rule 15 activation attestation

- **Integrated and enabled in source.** The normal `aq-land` CLI executes all four changes without a feature flag.
- **End-to-end validation boundary.** The suite invokes the CLI against temporary real Git repositories and stubs GitHub, reviewers, and Tier0. It checks the failure journal, failed-gate retry and outcome receipt, and the merge decision.
- **Observable and intervenable.** The failure journal includes the branch, head, and run identifiers. Existing blocker logs and stop messages support diagnosis. Operators can fix the blocker and rerun `aq-land` using its existing checkpoint.
- **Deferred 2026-11-24.** Integration review, live deployment, production end-to-end verification, and live PM tracking are deferred to orchestrator closeout. This evidence covers the isolated delegation worktree.

## Rollback

Revert the slice through the normal integration workflow. Existing journals and receipts can be retained as historical evidence. The slice requires no data migration.
