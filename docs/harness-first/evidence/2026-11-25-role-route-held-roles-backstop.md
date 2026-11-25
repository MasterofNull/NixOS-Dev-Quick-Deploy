# aq-role-route backstop keeps Gemini out of held roles

## Objective

Address codex REQUEST_CHANGES on bf7f87344: a missing or unreadable lane-eligibility registry must not restore Gemini's revoked `orchestrator` and `binding-acceptance` grants.

## Workflow/Session IDs

- Reviews: codex-20261125-041131-rqqhqx, codex-20261125-060134-rujqcu, codex-20261125-090128-w17q1k (REQUEST_CHANGES, same finding).
- Orchestrator Simurg@claude/opus-5.5#d1203103; implementer Claude Sonnet 5.5 sub-agent.

## Delegation Decision

Two-file bounded fix; deadline 2026-11-26T00:00Z; Codex is the reviewer, so a Claude Sonnet implementer keeps authorship independent.

## Commands Executed

- `python3 scripts/testing/test-lane-eligibility.py`
- `python3 scripts/testing/test-agent-agnostic-router.py`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence

`HARDCODED_BACKSTOP_BLOCKS` now blocks gemini for implementer, orchestrator and binding-acceptance. Failsafe tests assert gemini is not chosen and is listed hard-ineligible for both held roles under missing and malformed registries. Both suites PASS; the rule18 invariant map now matches the registry.

## Rollback Plan

Revert the commit; the fallback returns to blocking gemini for implementer only.

## Residual Risk

Restoring a held role now needs both a registry grant and a code change to the backstop; that is intended until the owner restores the roles.

## Hint Feedback

None.
