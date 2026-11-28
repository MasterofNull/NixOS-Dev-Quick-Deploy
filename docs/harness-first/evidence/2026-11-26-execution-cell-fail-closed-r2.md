# Execution-cell runner: fail-closed follow-up (r2)

## Objective
Second pass on the execution-cell add-pid fail-closed slice (see `2026-11-26-execution-cell-add-pid-fail-closed.md`): keep the runner, perf harness and their tests consistent so a failed `add_pid_to_cgroup` quarantines the cell instead of running it unconfined, and clear the Python type gate diagnostic in `scripts/testing/test-execution-cell-runner.py` (`jsonschema` possibly unbound).

## Workflow/Session IDs
Headless bug-fix slice, worktree agent-ae0401d49b68d1ed2. No workflow run id; staged only, not committed.

## Delegation Decision
Direct bounded implementation by a Claude Sonnet 5.5 sub-agent on the orchestrator's assignment; no further delegation.

## Commands Executed
- `scripts/governance/tier0-validation-gate.sh --pre-commit` (read the failure from `tier0-seq.log`)
- Moved the `jsonschema` import guard so the module is only referenced after a successful import (early `return` after the skip).
- `python3 scripts/testing/test-execution-cell-runner.py`

## Validation Evidence
Failure before: basedpyright `reportPossiblyUnboundVariable` on `jsonschema` in the `except jsonschema.ValidationError` clause, plus the cross-surface contract gate (runtime change in `ai-stack/switchboard/execution_cell_runner.py` with no connected doc). After: the schema check is unchanged in behaviour (skip when jsonschema is absent, check pass/fail otherwise); this evidence file satisfies the cross-surface contract. Final tier0 result is recorded in the implementer report.

## Rollback Plan
Revert the staged files; behaviour returns to the previous runner and test shape. No config, schema or data migration.

## Residual Risk
A descendant that called `setsid` before a failed cgroup attach could escape the direct process-group kill; the cell is quarantined, not proven absent, so no containment proof is claimed.

## Hint Feedback
None.
