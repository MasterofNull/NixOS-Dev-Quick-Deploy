---
doc_type: prd
id: workflow-deviation-recovery
title: Workflow Deviation Recursive Recovery
status: draft
owner: hyperd
date: 2026-08-08
priority: P0-high
---

# Workflow Deviation Recursive Recovery

## Problem

AQ-OS detects failures in several disconnected places, but a deviation from
`.agent/WORKFLOW-CANON.md` does not reliably enter one recursive-learning
lifecycle. `aq-loop` waits until retry exhaustion, delegation feedback is a
separate PRSI source, reviewer revisions remain document-local, and managed
agents can lose RESUME/PULSE writes when the event path is not writable.

The live hourly autonomous-improvement service demonstrates the consequence:
metric collection fails on the obsolete `routing_log` schema, the cycle prints
"system healthy", and systemd records exit success. The system suppresses the
very evidence intended to improve it.

## Required lifecycle

```text
detect -> preserve evidence -> deduplicate -> issue upsert
       -> learning candidate -> bounded shadow repair
       -> independent verification -> promote | reject | park | escalate
```

One closed `aq.workflow-deviation.v1` record is the interchange contract. It
contains reason codes and content hashes, never prompts, secrets, arbitrary
argv, stack dumps, or high-cardinality provider text.

## Safety boundary

Automatic work is allowed only when the classifier proves `mutation_risk` is
`none` or `low`, the action is reversible and repository-local, and no owner
authority is named. Runtime authority, security policy, secrets, deployment,
release/commit state, destructive operations, live traffic, or external side
effects always produce `approval_required` or `parked`; they are never
auto-applied.

Observation failure is not health. Missing evidence, malformed deviation
records, unavailable event writers, and failed remediation validation all fail
closed and remain visible.

## Slices

- **C0 — contract:** closed schema, pure classifier/resolver, golden vectors,
  focused tests. No writers, daemons, routing, PRSI mutation, or live adoption.
- **C1 — adoption:** emit from `aq-loop` and autonomous-improvement, broker or
  spool append-only receipts, deduplicate in PRSI, distinguish observation
  failure from healthy/no-trigger, and correct routing-metric schema drift.
- **C2 — Service Coverage:** Phase-0 integration check, command-center state,
  recurrence metrics, release evidence, and live dogfood.

### C1 adoption boundary

C1 is delivered in two atomic parts. **C1A** is the accepted host-producer and
shadow-intake repair: it corrects the live routing-metric schema, makes failed
observation non-success, persists validated receipts, and makes `shadow_only`
non-executable at both approval and execution selection. **C1B** adds the
missing confined-caller transport. A dedicated, host-owned AF_UNIX receipt
broker is the sole writer for agent-originated deviation receipts; clients
submit one closed record and receive a bounded typed acknowledgement. It is not
an agent dispatcher, workflow engine, event projector, or provider adapter.

The broker may trust a socket group and `SO_PEERCRED` only for local admission,
not as proof of reasoning-lane identity. Submitted records remain untrusted,
deduplicated observations and can create only non-executable shadow candidates.
The residual same-user attribution limitation remains explicit until the
state-spine/credential authority supplies per-lane cryptographic identity.

C1B also amends C1A's append helper in place so host and broker producers share
one receipt-inode lock and one validate/scan/conflict/replay/append/fsync
algorithm. Lock sharing without shared idempotency is insufficient: a direct
host producer could otherwise append the same ID after the broker released its
lock. Existing C1A callers retain fail-closed behavior and may safely ignore
the new `stored|replayed` return value.

## Acceptance

1. Identical deviations produce the same ID and one issue key.
2. Evidence or subject changes produce a distinct record without losing the
   stable root-issue grouping.
3. Authority/release/security deviations can never be automatic candidates.
4. Observation failure can never resolve to healthy or exit success.
5. Every lifecycle state has a QA and dashboard projection by C2.
