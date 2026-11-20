# CI: pass PR_AUTHOR to the Advanced Parity Tooling job

## Objective
Unblock the Dependabot manifest-only PRs (#813-#816, #819-#821). After #836 and a rebase they pass
Syntax Validation but still fail Advanced Parity Tooling with "high-impact paths changed but no new
evidence file was added".

## Workflow/Session IDs
- Claude Code background session 0b56dbd9 (Simurg@claude/opus-5.5), branch `fix/ci-pr-author-parity-job`.
- Failing example: PR #815, job 135967662417 (Advanced Parity Tooling).

## Delegation Decision
A two-line mechanical workflow edit, done by the orchestrator. The root cause was traced from a CI log
in the same session, and a delegate would have to re-derive it.

## Commands Executed
- `gh pr checks` on #808 and #812-#821: Syntax Validation passes after the rebase; Advanced Parity Tooling fails on 7 PRs.
- `gh run view --job 135967662417 --log`: `check-harness-first-pr-evidence-gate.sh` FAIL on `ai-stack/mcp-servers/aidb/requirements.txt`.
- Reviewed the CI workflow test.yml: line ~469 sets `PR_AUTHOR` for the harness-first step; the `advanced-parity-tooling` job (`run-advanced-parity-suite.sh`, ~887) runs the same gate without it.

## Validation Evidence
Root cause: #836's exemption (`config/harness-first-policy.json` `dependabot_manifest_exemption`)
waives the evidence file only when `PR_AUTHOR == dependabot[bot]`. Only one of the two jobs that run
the gate received `PR_AUTHOR`. This change sets it on the parity suite step as well, with the same
expression. Pass criterion: Advanced Parity Tooling is green on the rebased Dependabot PRs.

## Rollback Plan
Revert this commit. Only the env var of one CI step changes.

## Residual Risk
None for non-Dependabot PRs: `PR_AUTHOR` is a human login there, so the exemption does not apply and
the gate behaves as before. Any other workflow that runs the evidence gate without `PR_AUTHOR` would
fail the same way; only test.yml runs it today.

## Hint Feedback
When an exemption depends on an env var, every job that runs the gate must set that variable. A CI
lint that requires `PR_AUTHOR` on any step that calls the evidence gate would catch this.
