# delegate-to-codex keeps the prompt's trailing newline in every context profile

Date: 2026-11-12

## Objective

Main was red: `test-delegate-wrapper-shell-safety.py` failed with `codex: prompt mangled` (the delivered prompt ended in `PYEOF`, the
test expects `PYEOF\n`). Find the exact cause, rule out shell injection, make the prompt arrive byte for byte in every profile.

## Workflow/Session IDs

- Branch `fix/codex-lean-prompt-safety` (worktree `.agents/delegation/worktrees/codex-lean-fix`), base main 11e6e7aec.
- Related: PR #746 (added `--context-profile`), PR #747 (put the test back in CI). Each passed alone.

## Delegation Decision

Direct fix by the orchestrator's sub-agent under an explicit top-priority instruction (main red, two-line change); no further delegation.

## Commands Executed

- `python3 scripts/testing/test-delegate-wrapper-shell-safety.py` (before: fail; after: ALL PASS)
- `python3 scripts/testing/test-delegate-codex-context-profile.py`
- `python3 scripts/testing/run-test-group.py tests-delegate`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`

## Validation Evidence

Root cause: `cmd_delegate` and the `--print-prompt` path captured the assembled prompt with `full_prompt="$(build_codex_prompt ...)"`.
Command substitution strips ALL trailing newlines, so a prompt ending in `\n` lost it. Not a heredoc or `printf %s` interpolation problem:
the heredocs are quoted (`<<'LEAN_EOF'`, `<<'FULL_EOF'`) and the prompt is appended with `printf '%s' "$prompt"`, passed as a single argv element.
It affected every profile (full and lean alike); the test's prompt is short and safe mode, so auto chose lean. The `PYEOF` in the failure
text is the prompt's own last line (part of NASTY_PROMPT), not an extra line.

Injection: none. Prompt text is never parsed by the shell; the test asserts no `PWNED*` file under the sandbox or cwd, and it holds.
The only deviation was the dropped trailing newline.

Fix: capture with a sentinel, `x="$(build_codex_prompt ...; printf x)"; x="${x%x}"`, at both call sites in `scripts/ai/delegate-to-codex`.
Test not weakened; new `check_codex_context_profiles` asserts explicit full, explicit lean and auto (short prompt) each deliver the exact
prompt (ends with it, appears once) with no PWNED file.

Results: shell-safety test ALL PASS (includes codex/full, codex/lean, codex/auto); context-profile test 4 PASS;
`tests-delegate` 14/14 passed; check-ci-test-coverage PASS (779 tests: 660 declared, 119 exempt).

## Rollback Plan

Revert the two-line change in `scripts/ai/delegate-to-codex` and the new test function; no state or config involved.

## Residual Risk

`--prompt-file` still reads via `$(cat file)`, which strips trailing newlines of the input before assembly. That is input normalisation,
not wrapper mangling, and no test depends on it. tier0 was not run (instructed); the parent runs it at commit.

## Hint Feedback

No aq-hints were queried; the failure message plus the wrapper source were sufficient.
