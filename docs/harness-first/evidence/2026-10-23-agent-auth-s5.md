# Agent-auth AUTH-S5 (2026-10-23)

## Objective

Implement slice `AUTH-S5` (Enforcement per family, guided deny bodies, lockdown mode) under `.agents/plans/agent-auth/DESIGN.md`:
- Mode activation: Enable real enforcement (`enforce`) and emergency system freeze (`lockdown`).
- Guided deny bodies: Standardized JSON deny payload containing actionable guidance, rationale, and remediation hints for rejected routes.
- Lockdown mode: Allow read/health inspection requests while blocking all mutating requests (`POST`, `PUT`, `DELETE`, `PATCH`).

## Workflow/Session IDs

- Branch: `feat/wave19-agent-auth-s5`
- Design SSOT: `.agents/plans/agent-auth/DESIGN.md`
- Tracker: `.agents/plans/agent-auth/tracker.json` (item AUTH-S5)

## Delegation Decision

Implemented directly in `ai-stack/mcp-servers/hybrid-coordinator/middleware/authz.py` with unit tests in `scripts/testing/test-agent-auth-s5.py`.

## Commands Executed

```bash
python3 scripts/testing/test-agent-auth-s5.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence

- Unit test suite: `scripts/testing/test-agent-auth-s5.py` passed (4/4 PASS).
  - Enforce mode allows sanctioned routes (`read.hints`).
  - Enforce mode returns HTTP 403 with `guided_deny` on unauthorized routes (`workflow/run/start`).
  - Lockdown mode allows `GET /health` reads.
  - Lockdown mode blocks `POST /memory/store` writes with `reason=lockdown_active`.
- Updated `.agents/plans/agent-auth/tracker.json`: marked AUTH-S5 as SHIPPED.

## Rollback Plan

Revert the commit `feat(agent-auth): implement AUTH-S5 enforcement and lockdown mode`.

## Residual Risk

In enforce mode, clients lacking mapped policy scopes receive HTTP 403; mitigated by the preceding AUTH-S7 UDS client migration with transparent fallback.

## Commit subject and detection

`feat(agent-auth): implement AUTH-S5 enforcement and lockdown mode` (matches `feat(agent-auth): .*AUTH-S5`).

## Hint Feedback

No hints or issues encountered.

## Owner activation command

No privileged owner activation required; pure middleware and test enhancement.
