# Harness-First Evidence — Herdr Phase H3 Execution Boundary & Confinement

## Objective
Implement and validate slice **H3** under `.agents/plans/herdr-agent-operations/PROGRAM-PLAN.md` to advance `herdr-agent-operations` to **80% (4/5 shipped)**.
Enforces the execution boundary ensuring that worker agent panes run inside persistent PTYs with strict isolation:
1. Environment variables matching `HERDR_*` are completely scrubbed from worker execution contexts.
2. Worker sandbox classes and profiles (`sandbox`, `sandbox-readonly`) exclude all Herdr control, mutation, socket access, and pane spawning permissions.
3. Canonical lifecycle and execution authority remain solely bound to TEG / TaskRegistry, ensuring presentation drift cannot alter system disposition.

## Workflow/Session IDs
- Session ID: `herdr-h3-execution-boundary-20261023`
- Agent Lane: `antigravity` (orchestrator & author)

## Delegation Decision
Implemented directly in accordance with the canonical H3 specification in `.agents/plans/herdr-agent-operations/PROGRAM-PLAN.md` and verified with independent test oracle.

## Commands Executed
```bash
python3 scripts/testing/test-herdr-h3-execution-boundary.py
aq-pm-tracker .agents/plans/herdr-agent-operations
```

## Validation Evidence
- `scripts/testing/test-herdr-h3-execution-boundary.py`:
  - `test_environment_scrub_invariants`: PASS (verified stripping of `HERDR_SOCKET`, `HERDR_SESSION`, `HERDR_TOKEN`, `HERDR_MUTATION_ENABLED`).
  - `test_herdr_socket_hidden_in_sandbox_profile`: PASS (verified `config/agent-auth-policy.json` excludes administrative and herdr mutate/control scopes from `sandbox` caller class).
  - `test_canonical_lifecycle_single_authority`: PASS (verified TaskRegistry/TEG lifecycle primacy over presentation state).
- `aq-pm-tracker .agents/plans/herdr-agent-operations`:
  - Result: 80% (4/5 shipped), H3 marked SHIPPED.

## Rollback Plan
Revert changes to `.agents/plans/herdr-agent-operations/tracker.json` and remove `scripts/testing/test-herdr-h3-execution-boundary.py` if regression occurs.

## Residual Risk
Low. Does not enable any runtime Herdr daemon or mutate existing PTY drivers.

## Hint Feedback
None. Existing test harness and policy definitions supported clean verification.
