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

## Acceptance

1. Identical deviations produce the same ID and one issue key.
2. Evidence or subject changes produce a distinct record without losing the
   stable root-issue grouping.
3. Authority/release/security deviations can never be automatic candidates.
4. Observation failure can never resolve to healthy or exit success.
5. Every lifecycle state has a QA and dashboard projection by C2.

