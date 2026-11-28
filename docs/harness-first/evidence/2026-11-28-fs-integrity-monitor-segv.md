# fs-integrity-monitor SEGV: stream the journal scan, bound the unit

## Objective

Root-cause and fix `fs-integrity-monitor.service` failing every run with `status=11/SEGV` after 5-6 min and 5.2-6.0 GB peak memory (host budget 27 GB, unit had no MemoryMax).

Root cause: `fs-integrity-check` stored four whole-boot journals (`journalctl -b`, `-k -b`, `-b -1`, `-k -b -1`) in bash variables and concatenated them into `combined_logs`. The current boot's journal alone is 1,094,588,238 bytes of text (`journalctl -b | wc -c`); the journal on disk is 1.9 GB. Bash copies the text several times (command substitution, concatenation, `echo "$x" | grep`), reached ~6 GB, and crashed in `remove_quoted_nulls` during `expand_string_assignment` (core dump trace in the journal). Producer fix: stream each journal through `grep -c`, holding no log text in shell memory.

## Workflow/Session IDs

Simurg@claude/sonnet-5.5, headless delegate, worktree branch `worktree-agent-ad616ddec898cdb63`. Orchestrator session id not supplied. Changes staged only, not committed.

## Delegation Decision

Bounded single-slice work handed down by the orchestrator; no further delegation.

## Commands Executed

- `journalctl -u fs-integrity-monitor.service --since -2d -o cat` (crash trace, 5.9G memory peak, 1.6G read)
- `journalctl -b | wc -c` (1.09 GB), `journalctl --disk-usage` (1.9G)
- `nix-instantiate --parse nix/modules/core/fs-integrity-monitor.nix`
- `shellcheck scripts/health/fs-integrity-check.sh`
- `python3 scripts/testing/test-fs-integrity-monitor-bounded.py`
- same test with `FS_INTEGRITY_SCRIPT=<pre-fix script from HEAD>`
- manual runs of the three cases in `tests/unit/fs-integrity-helpers.bats` (bats is not installed here)
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`

## Validation Evidence

- Fixed script, new test (256 MiB `ulimit -v`, fake journalctl emitting 4 x 120 MB): 3 tests OK in about 1 s.
- Pre-fix script, same test: FAIL (2 of 3 tests), `xrealloc: cannot allocate 240000000 bytes`, and the signature case never reports the repair hint.
- Existing helper behaviours (`FS_INTEGRITY_LOG_TEXT` match returns exit 2 with the by-uuid hint; no match returns exit 0) still pass.
- shellcheck clean; `nix-instantiate --parse` OK; ci-checks coverage PASS.
- A full run against the real 1.09 GB journal did not finish within 100 s here (journalctl read time dominates); the unit TimeoutSec is 900 s. Real-journal peak RSS was not measured; the memory-capped synthetic test is the evidence.

## Rollback Plan

Revert the commit. The unit returns to the previous inline script, which crashes. A runtime-only rollback is not possible; this is a declarative Nix change applied on the next rebuild (owner act).

## Residual Risk

- The module now reads `scripts/health/fs-integrity-check.sh` via `builtins.readFile`, so the script is the single source and ships through writeShellApplication (shellcheck-gated at build).
- `MemoryMax=512M` and `MemorySwapMax=0` are an estimate for a streaming grep; if the unit is OOM-killed at that limit, raise it deliberately.
- The pattern includes broad strings such as `status=1/FAILURE` and `status=4`; with real journals these can match unrelated service failures and cause false exit 2. Not changed here (out of scope); worth a follow-up.
- Scanning four whole-boot journals every 60 min is I/O heavy even when streamed; now `Nice=19`, idle IO and CPU scheduling. A `--since` window is a possible future reduction.
- Takes effect only after rebuild (`aq-deploy-current`); not applied live.

## Hint Feedback

No aq-hints were queried for this slice; the journal crash trace and a direct read of the script located the cause.
