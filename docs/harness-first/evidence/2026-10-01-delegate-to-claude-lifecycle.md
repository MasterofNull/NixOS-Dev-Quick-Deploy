# Evidence — delegate-to-claude terminal reconciliation + admission control (2026-10-01)

## Objective
Close backlog items claude-blocking-mode-has-no-progress-or-terminal-reconciliation (critical) and claude-parallel-implementer-shared-quota-exhaustion (high).

## Root cause
`set -euo pipefail` + blocking `"${cmd[@]}" | tee` + PIPESTATUS: a nonzero provider exit or signal aborted the wrapper before any terminal registry write (rows stuck "running"); no pid/heartbeat; unlocked read-truncate-write registry updates; no cap/concurrency limit.

## Change
Provider runs as a tracked child (pid, wrapper_pid, heartbeat_at refreshed every DELEGATE_CLAUDE_HEARTBEAT_S); EXIT/TERM/INT trap always records a terminal state with exit_code. Registry writes under `<registry>.lock` (the same lock file task_registry.py uses) with atomic replace, in the wrapper and the background worker. Admission: DELEGATE_CLAUDE_DAILY_DISPATCH_CAP (40/UTC day), DELEGATE_CLAUDE_MAX_PARALLEL (2) flock slots with slot 0 reserved for reviewers; refusals exit 3 before a row is written; --force-budget, --budget-check-only.

## Validation
test-delegate-to-claude-lifecycle 7/7 (stub provider); model-routing 4/4 (x3 after a heartbeat-pipe hang fix), dispatch-payload-safety 2/2, agent-ops-projection 122/122.

## Follow-up
Consolidate the wrapper's inline registry helpers onto task_registry.py's transactional writer (same lock file, so behaviour is already serialized).

## Rollback
Revert the commit.

## Agents
Implementer: Claude Sonnet (worktree). Review: Claude Opus.
