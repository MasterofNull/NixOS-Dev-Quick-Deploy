# Evidence — transactional delegation registry + confirmed cancel (2026-10-01)

## Objective
Close backlog items delegation-registry-writers-not-transactional (critical), m2a-candidate-cas-barrier-and-tempfile-enforcement-gaps (high), and the cancellation half of local-dogfood-late-invalid-edit-after-time-budget (high).

## Root cause
`scripts/ai/lib/task_registry.py`: `_locked_rewrite` truncated (`open("w")`) before taking flock; append/update paths shared no lock (lost rows); M2A wrote a fixed `.tmp` with O_TRUNC, no O_EXCL/O_NOFOLLOW, one unchecked os.write; `expected_revision=None` skipped CAS; `cmd_cancel` marked cancelled right after SIGTERM.

## Change
`_atomic_write_bytes` (unique temp in same dir, O_EXCL|O_NOFOLLOW, full write loop, fsync, os.replace, dir fsync); one shared `<registry>.lock` for rewrite/append/update/M2A; revision mandatory for attach_process/transition_m2a (and `aq-delegation-registry --expected-revision`); cancel = TERM process+group -> grace (TASK_CANCEL_GRACE_S, 10s) -> KILL -> confirm death -> `cancelled`, else `cancel-failed` + detail.

## Validation
test-task-registry-transactional (8: concurrent writers lose nothing, reader never sees truncation, symlink not followed, CAS rejects stale/missing, TERM->KILL escalation, cancel-failed); test-agent-ops-projection 122 (call sites given explicit revisions, no assertion loosened); local-delegation-artifact, delegate-failure-classification, worktree-isolation, rsi-hung-delegate pass.

## Rollback
Revert the commit.

## Agents
Implementer: Claude Sonnet (worktree). Review: Claude Opus.
