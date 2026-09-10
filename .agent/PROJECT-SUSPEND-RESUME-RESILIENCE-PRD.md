# AQ-OS Suspend/Resume Resilience PRD

**Status:** ACTIVE — SR-1 contract slice
**Owner:** AQ-OS orchestrator
**Observed trigger:** a lid-close suspend interval overlapped a `llama-cpp`
stop/restart timeout and aborted an otherwise valid system deployment.

## Problem

AQ-OS runs long-lived inference services, agent dispatches, dogfood loops,
training jobs, and multi-step deployment operations on a mobile workstation.
Closing the lid is an expected operating-system event, not an operator error.
Today, individual components have useful recovery mechanisms, but there is no
single contract that requires every new managed workload to preserve state,
reconcile after resume, bound readiness waits, report a typed outcome, and make
that outcome visible to QA and the dashboard.

The observed timing is evidence of a suspend/restart race, not proof that lid
closure was the sole cause. The contract therefore covers suspend, hibernate,
process restart, transient service loss, and clock discontinuities without
disabling normal power management.

## Goal

Make interruption resilience a delivery requirement for every new or materially
changed long-running AQ-OS service or resumable operation. A workload may not
claim `suspend-safe` or `resumable` unless its machine-readable record and
evidence pass the governance gate.

## Non-negotiable development rule

Lid-close suspend and configured hibernation remain enabled. Every managed
long-running daemon, inference request path, agent loop, timer-triggered job, or
multi-step development/deployment operation must declare, in the same slice:

1. its interruption class and resume policy;
2. state safety through restartability, checkpointing, and/or idempotency;
3. graceful signal/cancellation behavior;
4. a bounded readiness or reconciliation deadline—never an infinite wait;
5. typed terminal outcomes such as `ready`, `resumed`, `interrupted`, and
   `timeout` rather than treating every interruption as a generic failure;
6. low-cardinality telemetry plus dashboard and live QA evidence;
7. a truthful implementation/compliance state. Planned behavior must never be
   represented as implemented.

New managed workloads must include an `AQ_SUSPEND_CONTRACT: <id>` marker and a
matching record in `config/suspend-resume-workloads.json`. Changes to registered
implementation paths trigger the focused validator. Tier-0 rejects missing,
malformed, inconsistent, or unsupported claims.

## Delivery slices

### SR-1 — executable development contract (this slice)

- Add the versioned workload inventory.
- Add a deterministic semantic validator and Tier-0 extension.
- Reject new managed service/timer declarations that omit a same-slice registry
  update.
- Add the stable rule to the canonical workflow and agent guidance.
- Record current known workloads honestly as partial or blocked.

### SR-2 — active-operation interruption safety

- Make deploy-time memory relief tolerate a stop/restart race without silently
  losing restoration intent or misclassifying a resume event.
- Persist the deployment phase needed for safe retry/reconciliation.
- Emit typed evidence for `paused`, `already_inactive`, `stop_interrupted`,
  `restored`, and `restore_failed`.

### SR-3 — system resume reconciler

- Add one idempotent post-resume reconciler for registered managed daemons and
  resumable jobs.
- Reuse the existing bounded 180-second inference readiness behavior.
- Publish typed outcomes to the dashboard and add an `aq-qa` integration check.

### SR-4 — dogfood/training continuity

- Add signal-safe dogfood checkpointing and `--resume` reconciliation.
- Prevent duplicate dispatch after a clock jump or stale process identity.
- Validate a real suspend/resume or controlled equivalent with the local model.

## Scope exclusions

- No suspend inhibitor, lid policy change, or blanket service restart.
- No claim that current dogfood or training behavior is fully compliant.
- No raw prompt, secret, checkpoint content, or high-cardinality task ID on the
  dashboard.
- No unsafe automatic retry of a non-idempotent external action.

## Acceptance criteria

- Registry JSON is schema/semantics validated and names existing evidence paths.
- False `compliant` and false `blocked` claims fail.
- A newly added managed service/timer or explicit workload marker without a
  staged registry update fails.
- Focused CI runs for likely managed-runtime implementation paths.
- Tier-0 discovers and executes the extension.
- Workflow documentation states the rule and links its executable contract.
- Existing suspend/hibernate behavior is unchanged.
- Exact-subject independent review passes before commit.

## Security and privacy

Checkpoint and resume metadata are untrusted input. Validate ownership, path,
schema, age, and attempt identity before reuse. Do not serialize credentials,
raw prompts, tool outputs, or database secrets into checkpoints or telemetry.
Reconciliation must be least-privilege, idempotent, rate-bounded, and unable to
promote an agent's authority after restart.

## Rollback

Revert the SR-1 commit to remove the registry and gate. This changes governance
only and does not alter lid, suspend, hibernate, or live service behavior.
