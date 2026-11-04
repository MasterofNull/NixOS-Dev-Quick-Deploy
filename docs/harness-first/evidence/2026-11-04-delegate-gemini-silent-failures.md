# Delegate-to-gemini silent failures (2026-11-04)

## Objective
Remove three silent failures in `scripts/ai/delegate-to-gemini`. First, `_gemini_meaningful_bytes()` printed "0" twice when all output was filtered noise, which broke the caller's arithmetic. Second, a prompt of 131072 bytes or more failed at exec (E2BIG) with no explanation. Third, the CLI flag mapping had no regression test. Fourth, in `--wait` mode a non-zero Gemini exit killed the wrapper at the `| tee` pipeline under `set -e` and pipefail, so the failed and partial-success handling never ran.

## Workflow/Session IDs
- Branch: `fix/delegate-gemini-silent-failures`, from `origin/main`.
- Backlog item closed: DELEGATE-GEMINI-ARGMAX-SILENT.
- Supersedes the uncommitted fixes in `/tmp/wt-gemini-output-counter` and `/tmp/wt-gemini-headless-mode` (Antigravity/Codex, 2026-11-02/03).

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet, as a bounded slice under Rule 17. The earlier uncommitted fixes were read for ideas only. The `auto_edit` value expected in the older test was wrong, because the CLI receives `accept-edits`.

## Commands Executed
- `bash -n scripts/ai/delegate-to-gemini`
- `shellcheck scripts/ai/delegate-to-gemini`
- `python3 scripts/testing/test-delegate-wrapper-shell-safety.py`
- `python3 scripts/testing/test-agent-action-policy.py`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`

## Validation Evidence
- `bash -n` passes. Shellcheck is unchanged at SC1091 x4 and SC2094 x3.
- The shell-safety test passes in full (ALL PASS). It now covers the mode mapping (yolo to auto, auto_edit to accept-edits, plan to plan, no `--approval-mode`), noise-only output, and an oversize prompt.
- Against the old script the noise-only test fails with the bash arithmetic error, so it guards the regression.
- `test-agent-action-policy.py` passes (7/7). `check-ci-test-coverage.sh` passes.
- The `--wait` fix wraps the pipeline in `set +e` / `set -e` and reads `PIPESTATUS` right after. The failed branch now returns the provider exit code, so the wrapper exits non-zero. A test with a stub exiting 3 checks the exit code, the registry status `failed`, and the stub stderr in the task log.
- The oversize check runs twice: on the raw prompt before the A2A gates, and on the full prompt before launch. The secret scan passes the prompt through an environment variable, which has the same per-string limit, so the check had to come first.

## Rollback Plan
Revert the commit. Both changed files are self-contained and nothing else depends on the new helper.

## Residual Risk
- The size limit is the Linux per-argument constant. It is not derived at runtime.

## Hint Feedback
No hints were consulted. The environment-variable path of the secret scan sharing the argv limit was found by running the test, not from a hint.

## Follow-up commit

`scripts/ai/lib/gemini-background-worker.sh` had the same byte-counter bug (`|| echo 0` under pipefail, line 34), found by Gemini review `gemini-20261104-094403-fftrqd` (LOW). Fixed the same way (`|| true`). Scratch reproduction: old form gives `0\n0`, new form gives `0`.
