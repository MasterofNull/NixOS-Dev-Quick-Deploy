## Objective
Fix the stale MCP server source path in the MCP integrity baseline and check scripts. The default `MCP_SERVER_DIR` resolved to `scripts/ai-stack/mcp-servers`, so `find` failed on manual runs. The baseline updater also had no guard against an empty file list, so a directory with no `.py` files could overwrite a good baseline.

## Workflow/Session IDs
Branch fix/mcp-baseline-path, worktree `.agents/delegation/worktrees/mcp-baseline`. Date 2026-11-06.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Haiku (Rule 17, mechanical bounded edits in two scripts, one test file, one evidence doc). The systemd unit sets `MCP_SERVER_DIR`, so the production timer was not affected; only manual runs were.

## Commands Executed
- Read `scripts/security/update-mcp-integrity-baseline.sh`, `scripts/testing/check-mcp-integrity.sh`, `scripts/testing/test-mcp-integrity-baseline.sh`, `scripts/testing/test-mcp-integrity-unit-path.sh`.
- Edited the default path in both scripts to `$(cd "$(dirname "$0")/../.." && pwd)/ai-stack/mcp-servers`.
- Updater: after the file list is built, exit 1 with a message naming `MCP_SERVER_DIR` if the count is 0. The baseline is not touched.
- Checker: `missing_files` and `changed_files` are emitted as `[]` when empty instead of `[""]`.
- Test: added cases (a) default path with `MCP_SERVER_DIR` unset, writing to a temp baseline, (b) empty directory refuses and leaves an existing baseline byte-identical, (c) alert `missing_files` is `[]` when nothing is missing.
- `bash scripts/testing/test-mcp-integrity-baseline.sh`
- `bash scripts/testing/test-mcp-integrity-unit-path.sh`
- `shellcheck --severity=warning scripts/security/update-mcp-integrity-baseline.sh scripts/testing/check-mcp-integrity.sh`
- `./scripts/governance/run-ci-checks.sh --changed --base refs/remotes/origin/main`

## Validation Evidence
Root cause: the `..` in the default path was one level short. The script lives in `scripts/security/` and `..` resolves to `scripts/`, not the repo root.

Results:
- test-mcp-integrity-baseline.sh: `PASS: mcp-integrity missing/empty/malformed baseline is non-ok, tamper alerts, baseline never auto-created; default path, empty-dir refusal, empty missing_files verified` (rc=0)
- test-mcp-integrity-unit-path.sh: `PASS: ai-mcp-integrity-check unit declares pkgs.jq and pkgs.coreutils` (rc=0)
- shellcheck --severity=warning on both scripts: no output, rc=0
- run-ci-checks.sh --changed: `run-ci-checks: 8 pass, 0 fail, 0 warn` (rc=0)

## Rollback Plan
Revert the changes to the two scripts, the test file and this evidence file. No data or config migration is involved. The real baseline file was not touched by any run.

## Residual Risk
- `MCP_SERVER_DIR=""` (set but empty) still falls back to the default path, as before. Only a directory that exists with zero `.py` files, or a missing directory, now refuses. A missing directory already failed under `pipefail`.
- The `changed_files` array got the same `[]` fix as `missing_files`, since it had the same `[""]` defect when empty.

## Hint Feedback
No hints were consulted. The script comments and the existing test file were the useful context.
