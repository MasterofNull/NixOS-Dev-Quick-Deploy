# Local delegation latency observability

## Problem and objective

The existing-profile READY probe `local-20260916-130836-58d3m6` returned
1255 input / 2 output tokens with a 286.1-second progress receipt. That duration
includes slot waiting and request execution. The receipt's token rate is not
decode throughput. Missing phase timestamps prevent retrospective decomposition.
Expose the measured duration and its limitations in the existing operator monitor
before attempting performance changes.

## Scope and minimal-code decision

Reuse `TaskRegistry.monitor_payload`, its existing dashboard monitor card and
QA 0.10.9 fixture (rung 2). No new service, metric authority, dependency or endpoint.
Implementer owns only `scripts/ai/lib/task_registry.py`, `assets/dashboard.js`
and `scripts/testing/test-local-delegation-artifact.py`.
Read progress metadata with a bounded, no-symlink regular-file inspection. Project
only a finite nonnegative elapsed value and explicitly unavailable decomposition.
Never include receipt content, prompts or arbitrary keys in the new projection.
No registry rewrite or task status change is permitted by this measurement.

## Acceptance criteria

- Monitor tasks expose measured pipeline elapsed seconds when a valid matching
  local-direct progress sidecar supplies them; otherwise null with an explicit
  unavailable indication. No inferred queue, prefill, TTFT or decode values.
- Dashboard shows pipeline time, not a misleading decode rate, and explains that
  queue/prefill/generation breakdown is not recorded.
- Fixtures exercise valid zero/positive values and absent, malformed, nonfinite,
  negative, boolean, oversized, symlink and non-local receipts without leaking data
  or changing registry/status semantics.
- Existing QA 0.10.9 remains the integration gate; fixture and syntax checks pass.
  Independent non-author exact-subject review and staged Tier-0 precede commit.
- A second unchanged-profile read-only READY task supplies a separate live baseline;
  do not label it warm/cold without evidence or claim coding-quality promotion.

## Security, exclusions and rollback

Bound file reads; fail to unavailable on inspection uncertainty. No secret output.
Frozen `dispatch.py`, payload/model settings, admission, sleep, protected manifests,
service restart/rebuild, push and canonical provider projection are out of scope.
Production phase instrumentation requires its own protected-manifest authorization.
Rollback is a separately authorized revert of this atomic additive projection;
historical receipts and registry remain untouched. Live dashboard activation is
separate from source validation. User resumption authorizes this bounded repo slice.

## Plan disposition

PLAN_READY_WITH_FOLLOWUPS: metadata-only source investigation establishes that the
duration is real and decomposition absent. Defer protected producer instrumentation
and optimization until correlated timing exists; do not reopen prior accepted slices.
