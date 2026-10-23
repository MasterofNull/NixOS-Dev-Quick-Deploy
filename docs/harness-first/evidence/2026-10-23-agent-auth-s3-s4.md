# Agent-auth AUTH-S3 and AUTH-S4 (2026-10-23)

## Objective

Implement slices `AUTH-S3` (hardened UDS peer identity resolution) and `AUTH-S4` (Switchboard / API-key containment transport) under `.agents/plans/agent-auth/DESIGN.md`:
- AUTH-S3: UnixSite agent listener, raw SO_PEERPIDFD (77), full cgroup path match, fail-to-unknown.
- AUTH-S4: Switchboard / API-key containment over agent.sock via httpx UDS, aq_http client helper with peer_gone retry.

## Workflow/Session IDs

- Branch: `feat/wave10-agent-auth-s3-s5`
- Design SSOT: `.agents/plans/agent-auth/DESIGN.md`
- Tracker: `.agents/plans/agent-auth/tracker.json` (items AUTH-S3, AUTH-S4)

## Delegation Decision

Orchestrated directly by Antigravity with independent review trailers and verified local unit testing.

## Commands Executed

```bash
pytest ai-stack/tests/unit/test_peer_identity_s3.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence

- Unit test suite: `ai-stack/tests/unit/test_peer_identity_s3.py`: 5 passed in 2.35s
- Tier 0 pre-commit gate: 70 passed, 0 failed
- Pre-push quick lint gate: 22/22 checks passed
- SO_PEERPIDFD self-test verified functional on host Linux kernel 7.2.10

## Rollback Plan

Revert the commit `feat(agent-auth): implement AUTH-S3 UDS peer identity and AUTH-S4 transport containment`. The changes are non-destructive and isolated to `ai-stack/mcp-servers/shared/`.

## Residual Risk

Short-lived client connections terminating before `/proc/<pid>/cgroup` is read will fail closed to class `unknown`, which is caught and retried automatically by `AqHttpClient`.

## Commit subject and detection

`feat(agent-auth): implement AUTH-S3 UDS peer identity and AUTH-S4 transport containment` (matches `feat(agent-auth): .*AUTH-S3`).

## Hint Feedback

No issues or hints needed for UDS peer resolution.

## Owner activation command

No privileged owner activation required; pure repo and library enhancement.
