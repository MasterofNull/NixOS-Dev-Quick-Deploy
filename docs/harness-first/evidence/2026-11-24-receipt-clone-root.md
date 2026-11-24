# Receipt lookup from standalone clones

## Root cause

PR #864 (`aq-land-receipt-clone-root`) traced the receipt failure to Git root discovery. In a standalone clone, `git rev-parse --git-common-dir` points to the clone's `.git`. `MAIN_ROOT` therefore points to the clone, while `--registry` or `AQ_DELEGATION_DIR` can select the durable checkout's registry. A repo-relative `output_file` such as `.agents/delegation/outputs/rev.log` then resolves against a checkout that lacks the review log.

## Resolution and containment

`_git_common_root` accepts the parent of a resolved Git common directory named `.git`. `_allowed_scopes` checks registry provenance before the checkout and Git common roots. For a registry in `.agents/delegation`, it uses the durable checkout as the path base and confines resolved targets to `.agents/delegation`. This preserves the repo-relative receipt path across checkout types. A registry-directory scope also supports paths such as `outputs/rev.log` under custom delegation directories.

`_rel` checks containment after resolving paths and symlinks. For relative paths, it prefers the first existing contained target and reports an escape ahead of a missing-path fallback. Mint, verify, and branch audit pass the selected registry into this lookup.

## Local verification

The static analysis baseline was clean HEAD `c2160cc1f` in the assigned worktree before editing. Diagnostics were compared by file and message with line and column positions removed.

| Command | Result |
| --- | --- |
| `python3 -m py_compile scripts/ai/aq-review-receipt scripts/testing/test-aq-review-receipt.py` | Exit 0 with no output. Bytecode went to a temporary cache under `/tmp`. |
| `basedpyright scripts/ai/aq-review-receipt scripts/testing/test-aq-review-receipt.py` | `15 errors, 0 warnings, 0 notes` on both runs. All 15 diagnostics matched clean HEAD, with zero new diagnostics. The changed-tree run exited 1 for the existing errors. |
| `ruff check scripts/ai/aq-review-receipt scripts/testing/test-aq-review-receipt.py` | `All checks passed!` on both runs, with zero new diagnostics. The changed-tree run used `RUFF_NO_CACHE=true`. |
| `python3 scripts/testing/test-aq-review-receipt.py` | Exit 0. `Ran 44 tests in 22.858s` and `OK`. The run used `PYTHONDONTWRITEBYTECODE=1`. |

The suite uses real Git worktrees, standalone clones, and a local bare remote. It covers mint, publish, local and published verify, and branch audit from the linked worktree and standalone clones. Both standalone registry selection methods are exercised, including verification back in the durable checkout. Additional cases cover a custom registry directory and rejection of traversal, escaping symlinks (including a broken link), and an out-of-scope absolute path.

## Rule 15 activation attestation

- **Integrated and enabled.** The existing receipt CLI uses the resolver automatically in mint, verify, and branch audit when this revision runs.
- **Validated end to end locally.** The receipt lifecycle ran against real Git checkouts and a local bare remote. Canonical receipt paths survived publication and cross-checkout verification.
- **Observable.** Branch audit surfaced the CI-assertion warning from the durable review log, and out-of-scope paths produced `outside the repo or registry root` errors without minting receipts.
- **Intervenable.** Operators can select the registry with `--registry` or `AQ_DELEGATION_DIR` and inspect published receipt results with `audit --branch`.
- **Deferred on 2026-11-24.** The orchestrator owns landing, activation and verification in the running `aq-land` environment, and confirmation of live PM tracking. This isolated delegate run covers local activation and verification.

**Rollback.** Revert the slice through the normal PR workflow after landing. During rollback, use the durable checkout for receipt operations against its registry. The slice preserves the receipt schema and canonical paths for the durable registry.
