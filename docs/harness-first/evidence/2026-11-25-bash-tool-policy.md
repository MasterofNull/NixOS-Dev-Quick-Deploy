# Bash tool-contract policy (Claude lane)

## Objective

Enforce the tool contract ("never raw grep/ls/find/cat in shell commands", `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`) for the Claude lane with a PreToolUse Bash hook backed by a shared policy module (`scripts/ai/lib/bash_tool_policy.py`) that other lanes can call. Backlog: TOOL-CONTRACT-NOT-ENFORCED-IN-BASH.

## Workflow/Session IDs

Headless delegate slice, worktree `agent-a49427346cfd3a5b0`; no aq-session-start hydration (bounded implementer mode).

## Delegation Decision

Bounded implementer slice dispatched by the orchestrator to a Sonnet sub-agent (Rule 17). Not committed by the implementer; staged for orchestrator review.

## Commands Executed

- `python3 scripts/testing/test-bash-tool-policy.py`
- `python3 scripts/governance/check-cross-surface-contract.py`
- `GITHUB_BASE_REF=main bash scripts/testing/check-harness-first-pr-evidence-gate.sh`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`

## Validation Evidence

- Policy test: 14 command cases, kill switch, hook deny (exit 2, replacement named on stderr), hook allow, fail-open on invalid JSON, telemetry JSONL has no command text (`PASS`).
- Telemetry: `.agents/telemetry/bash-tool-policy.jsonl` records ts, decision, rule, first token only.
- Registration in `.claude/settings.json` (PreToolUse `Bash` matcher, next to aq-approval-ask-hook) must be applied by the owner: the agent edit was blocked by the host policy protecting hook configuration.

## Rollback Plan

Set `AQ_BASH_POLICY=0` (always allow), or remove the `aq-bash-tool-policy-hook` entry from `.claude/settings.json`.

## Residual Risk

Claude lane only; codex/gemini/local wrappers to adopt `bash_tool_policy.evaluate` in a follow-up per Rule 16. Parsing is quote-aware but heuristic: `$(...)` and subshell contents are not inspected, and `ls`/`grep` after `xargs`/`sudo`/`env` are not matched.

## Hint Feedback

No aq-hints were queried in this headless slice; none to report.
