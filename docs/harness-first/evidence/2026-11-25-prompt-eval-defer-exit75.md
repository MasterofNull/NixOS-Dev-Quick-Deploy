# aq-prompt-eval defers with exit 75 on consecutive timeouts

Restores the item PR #834 described but never committed.

- Root cause: a single llama slot; under saturation every eval case waits its full timeout, so the unit ran ~1h and failed.
- scripts/ai/aq-prompt-eval: AQ_PROMPT_EVAL_MAX_CONSECUTIVE_ERRORS (default 3) consecutive timeouts stop the run, write no score for the aborted prompt, and exit 75 (EX_TEMPFAIL). A success or non-timeout error resets the count; non-timeout error streaks still abort with exit 1.
- nix/modules/roles/ai-stack.nix: ai-prompt-eval has SuccessExitStatus = [0 75], so a deferral is not a unit failure; the next timer run retries.
- Tests: test-aq-prompt-eval-defer.py (new); test-prompt-eval-transport-guard.py now expects 75 for all-timeouts and still asserts the backend is called exactly the limit number of times.
- Activation: the Nix change takes effect on the next rebuild (owner act).

## Objective

Make `ai-prompt-eval` defer (exit 75, treated as success) when inference is saturated instead of grinding ~1h and failing.

## Workflow/Session IDs

- Implementer: Simurg@claude/sonnet-5.5#prompt-eval (worktree-agent-aef08342e49b58440, commit f44c7fb3a); orchestrator Simurg@claude/opus-5.5.

## Delegation Decision

Bounded three-file slice; Codex in quota cooldown, so routed to a Claude Sonnet implementer (Rule 17 default).

## Commands Executed

- `python3 scripts/testing/test-aq-prompt-eval-defer.py`
- `python3 scripts/testing/test-prompt-eval-transport-guard.py`
- `python3 -m py_compile scripts/ai/aq-prompt-eval`; `nix-instantiate --parse nix/modules/roles/ai-stack.nix`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence

Defer test 2/2 PASS, transport-guard 2/2 PASS, parse checks OK, tier0 72 passed / 0 failed.

## Rollback Plan

Revert the commit; the unit returns to failing on long timeout streaks. No data migration.

## Residual Risk

A persistently saturated slot now yields repeated deferrals with no score; observable through the deferral line and unit logs, not as a unit failure.

## Hint Feedback

None beyond the root cause: #834's commit body claimed this change but did not contain it, so verify claimed changes against the diff.

Mixed-run breaker and runtime-state regression cases pass (5/5 defer cases). The non-timeout breaker exited 0 before the repair and exits 1 after it.
