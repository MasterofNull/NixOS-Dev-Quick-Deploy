# delegate-to-gemini: match the current Gemini CLI flags

## Objective

Make `scripts/ai/delegate-to-gemini` run the installed Gemini CLI again. It defaulted `GEMINI_BIN` to the removed `~/.npm-global/bin/gemini` and passed `--approval-mode`, which the current CLI does not have, so every delegated Gemini task (for example the PR #676 reviews `gemini-20261102-*`, `gemini-20261103-*`) logged only the CLI help text and no result.

Fix:
- `GEMINI_BIN` defaults to `command -v gemini` (fallback `~/.local/bin/gemini`).
- Wrapper modes map to the CLI `--mode` flag: `yolo -> auto`, `auto_edit -> accept-edits`, `plan -> plan`.
- `plan` (read-only) is accepted by the wrapper and added to `gemini.allowed_modes` in `config/agent-action-policy.json`. It is strictly less privileged than the already-allowed modes; `yolo` stays the only privileged mode.

## Workflow/Session IDs

- Implementer: Claude Haiku (wrapper edit); policy line and evidence by orchestrator claude-opus, 2026-11-04.
- Live check: `gemini-20261104-012953-ovsmi2` (PONG).

## Delegation Decision

Mechanical single-file edit with a checkable result: Haiku (Rule 17). The one-line policy addition was done by the orchestrator because Haiku correctly stopped at the security-policy boundary.

## Commands Executed

- `bash -n scripts/ai/delegate-to-gemini`; `shellcheck scripts/ai/delegate-to-gemini`
- `python3 scripts/testing/test-delegate-wrapper-shell-safety.py`
- `python3 scripts/testing/test-agent-action-policy.py`
- `scripts/ai/delegate-to-gemini --mode plan --model gemini-3.8-flash-medium --wait --prompt "Reply with exactly the word PONG and nothing else."`

## Validation Evidence

- `bash -n` clean; shellcheck warnings identical before and after (SC1091 x4, SC2094 x3).
- Shell-safety test: `ALL PASS`. Policy test: `7/7 agent-action-policy tests passed`.
- Live run printed `PONG` and `Task gemini-20261104-012953-ovsmi2 completed successfully.`

## Rollback Plan

Revert the commit. Delegated Gemini runs return to printing CLI help (the prior broken state).

## Residual Risk

- The CLI's default model returned `RESOURCE_EXHAUSTED (429)` on 2026-11-04 (resets in about 130h); `--model gemini-3.8-flash-medium` works. The wrapper keeps no default model, so callers must pass `--model` until the quota resets.
- `test-delegation-local-gemini.py` exits 0 even when both profiles return HTTP 502, so it is not evidence of a pass (logged in issues-backlog).

## Hint Feedback

None.
