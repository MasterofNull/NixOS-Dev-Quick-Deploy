# Evidence — aq-approve single-use claim + actor identity (2026-10-01)

## Objective
Close backlog item attention-approval-pre-effect-fence-and-actor-auth-gap (critical).

## Root cause
`scripts/ai/aq-approve` ran the executor (AppArmor fix / drop-dispatch) before `attention_queue.resolve()`, which locked and checked `pending` only afterwards: concurrent approvals, or an approve racing reject/expiry, could all execute the effect. `resolved_by` was the literal "human".

## Change
`attention_queue.claim_for_execution()` (flock; pending -> executing; refuses non-pending/expired/missing) before any side effect; `finalize_claim()` -> approved | failed (terminal, never back to pending). Actor = OS user (`pwd.getpwuid`) + optional `--actor` label. Same pattern as the dashboard ACP fix (0ce74b99).

## Validation
test-aq-approve-single-use 5/5 (8 concurrent approvals execute once; approve after reject/expiry no-op; executor failure terminal; actor recorded). Existing: attention-queue-env-override 6/6, aq-report-attention-contention 5/5, delegate-attention-queue-wiring pass. test-boot-stability-regressions fails identically on main without this change (separate health-spider defect, filed).

## Rollback
Revert the commit.

## Agents
Implementer: Claude Sonnet (worktree). Review: Claude Opus.
