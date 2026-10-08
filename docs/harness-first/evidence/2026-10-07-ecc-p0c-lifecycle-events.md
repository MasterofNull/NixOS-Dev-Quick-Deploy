# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-ECC-P0C

## Objective
- ECC parity P0-C: typed lifecycle event adapter closing pre/post/failure/compact/stop event gaps safely. Ships dormant: no production handler is registered; no activation authority.

## Workflow/Session IDs
- Workflow ID: wf-ecc-p0c-lifecycle-events-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f (orchestrator); implementer is a worktree-isolated delegate.

## Delegation Decision
- Implementer: Claude Sonnet 5.5 (Rule 17 step-up from Haiku recorded by orchestrator: multi-file contract work). Not self-accepted; orchestrator plus a non-author lane review.

## Commands Executed
```bash
python3 scripts/testing/test-lifecycle-events.py
python3 scripts/testing/test-lifecycle-events.py --smoke
scripts/ai/aq-qa 0 --machine | rg 0.10.56
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- New files: scripts/ai/lib/lifecycle_events.py (schema, explicit registry, runner, health_summary), scripts/testing/test-lifecycle-events.py.
- Shared registration points only: QA 0.10.56 in phase0.py and _aq-qa-bash; read-only projection `capability_gap.lifecycle_events` in the existing /advanced/runtime-summary route plus two rows in the existing dashboard card (health, latency avg/max, failures, disabled).
- Tests cover: malformed/untrusted payloads, missing tool, timeout, crash under fail_policy open vs closed, lease-required policy, env isolation (fake secret built at runtime, not inherited), recursion suppression + loop budget, disabled list, backpressure, cancel, suspend/resume with tampered snapshot, telemetry counters.
- Adapter state file path comes from env LIFECYCLE_EVENTS_STATE_FILE; unset means status "dormant" with zero counters.
- Output of the runs is pasted in the commit handback report.

## Rollback Plan
- `git revert` the single commit; no units, config or runtime state were added. Optional state file is outside the repo and unused unless configured.

## Residual Risk
- Dormant: no live producer emits events and no handler is registered, so the dashboard shows "dormant" until P1 wires diagnostics. Handlers run as child processes with a minimal env but are not sandboxed beyond that (no namespace/AppArmor); registering a handler is an explicit code act and needs its own activation review. Capability-lease value is validated for shape only; enforcement stays with Foundation C.

## Hint Feedback
- No aq-hints consulted.
