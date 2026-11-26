# aq-qa phase 0 alert attn-605960e778644931 root cause

## Objective

Root-cause the health-monitor alert (aq-qa 0 failing 0.5.7, 0.6.1, 0.10.50), fix the producer of
the false failure, and make transient failures diagnosable from the alert alone.

## Workflow/Session IDs

- Orchestrator: Simurg@claude/opus-5.5#d1203103; implementer: Claude Sonnet 5.5 sub-agent (worktree-agent-acdffee6e4c2e1cd5).
- Monitor runs: passing through 2026-11-25T09:35Z; failing 09:44Z (3) and 10:00Z (2: 0.5.7, 0.6.1).

## Delegation Decision

Codex was in provider cooldown (resets 12:05Z) and the slice spans two files plus tests, beyond the
local single-edit envelope; routed to a Claude Sonnet implementer (Rule 17 default) with orchestrator review.

## Commands Executed

- `python3 scripts/testing/test-factory-gate-readiness.py` (0.10.50 fixture, exit 0 on main checkout)
- `run_provider_probe(..., canonical=True)` with the service PATH (`systemctl show ai-stack-health-monitor -p Environment`): all four providers pass
- aq-usage ledger scan 09:36Z-10:03Z: no concurrent aq-qa run in the main checkout (rules out probe-lock contention)
- `python3 scripts/testing/test-aq-report-editor-state-budgets.py`; `python3 scripts/testing/test-qa-phase0-bounded.py`

## Validation Evidence

- 0.5.7: `~/.vscode-oss/extensions/.obsolete` (mtime 2026-11-20) lists `anthropic.claude-code-2.1.187` and `-2.1.223`; neither directory exists. With the fix both resolve to `ignored_ai_markers` -> PASS. A marker whose dir exists still fails (test case kept).
- 0.6.1: not reproducible after 10:02Z under the service PATH; settings.json change ruled out (claude probe passes on current settings). The check now reports `provider=failure_class(exit N): stderr` (test asserts `codex=nonzero_exit(exit 3): boom`).
- 0.10.50: self-cleared at 10:00Z; failure now carries the fixture stderr/stdout tail.
- Both tests PASS; py_compile clean.

## Rollback Plan

Revert the commit; aq-report and phase 0 return to the previous strings and marker counting. No state or schema change.

## Residual Risk

0.6.1's 09:44Z/10:00Z cause remains unknown; the next occurrence will carry the evidence. The
health monitor still does not persist `.details`; the message now carries the summary instead.

## Hint Feedback

Hints did not cover the probe's `primary_user_path` vs. interactive PATH difference; a canonical
probe with `executable_path=None` gives a misleading `node: not found`, so reproduce with the unit's PATH.

The four-provider truncation and regular-file extension regressions failed before repair. Both focused test files pass after reserving provider summary space and checking for a directory.
