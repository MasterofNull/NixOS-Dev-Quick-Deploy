# Bash tool-contract policy (Claude lane)

## Objective

Enforce the tool contract ("never raw grep/ls/find/cat in shell commands", `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`) for the Claude lane with a PreToolUse Bash hook backed by a shared policy module (`scripts/ai/lib/bash_tool_policy.py`) that other lanes can call. Backlog: TOOL-CONTRACT-NOT-ENFORCED-IN-BASH.

## Contract

This is a best-effort efficiency nudge, NOT a security boundary. It denies only when a command segment is CLEARLY a bare read: the first word of a pipeline is exactly `cat`, `ls`, `find` or `grep` and, for `cat`, it reads named files (stdout redirect to a file, heredoc, `<<<`, stdin-only or `cat -` all allow). If tokenizing fails or is ambiguous (shlex ValueError, unbalanced quotes, unterminated constructs, unusual syntax) the command is allowed. False allows are acceptable; false denies must be rare. Tokenizing is stdlib `shlex` (posix, punctuation_chars) after the owner decision of 2026-11-26 replaced the hand-rolled parser (three review rounds kept finding edge cases in it). Ambiguity decisions that allow: unbalanced quotes to end of input, `/bin/cat` (first word not exactly `cat`), `cat < f`, and any `cat` with a redirect operator including stderr-only `cat f 2>/dev/null` (chosen for simplicity).

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

- Policy test: 57 command cases (incl. escaped heredoc delimiters, stdout vs stderr redirects, escaped/quoted `;` and quotes, comments with quotes, multi-line quotes, `>|`, unbalanced input allowed); telemetry rule/token is the offending segment's first word (`cd x && ls -la` logs `bare-ls`), bare-filename log path, kill switch, hook deny (exit 2, replacement named on stderr), hook allow, fail-open on invalid JSON, telemetry JSONL has no command text (`PASS`).
- Telemetry: `.agents/telemetry/bash-tool-policy.jsonl` records ts, decision, rule, first token only.
- Registration in `.claude/settings.json` (PreToolUse `Bash` matcher, next to aq-approval-ask-hook) was applied by the owner (2026-11-26) and is present in `.claude/settings.json` on this branch, not part of this staged delta (the agent edit had been blocked by the host policy protecting hook configuration).

## Rollback Plan

Set `AQ_BASH_POLICY=0` in the environment that launches the agent (always allow; owner act, environment-level only -- a per-call `AQ_BASH_POLICY=0 cmd` prefix does not bypass the policy and stays denied), or remove the `aq-bash-tool-policy-hook` entry from `.claude/settings.json`.

## Residual Risk

Claude lane only; codex/gemini/local wrappers to adopt `bash_tool_policy.evaluate` in a follow-up per Rule 16. Parsing is shlex-based and best-effort (see Contract): `$(...)` and subshell contents are not inspected, `ls`/`grep` after `xargs`/`sudo`/`env` are not matched, and an escaped backslash directly before an operator (`\\\\;`) is read as escaped (false allow).

## Hint Feedback

No aq-hints were queried in this headless slice; none to report.
