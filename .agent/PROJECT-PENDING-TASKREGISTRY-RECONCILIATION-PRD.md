# PENDING ↔ TaskRegistry Reconciliation F1

Status: implemented candidate; independent acceptance pending.

## Objective

Reconcile legacy `PENDING.json` rows marked `running` from the existing TaskRegistry process, heartbeat,
and artifact overlay. The reconciler is an explicit stewardship operation; it does not execute local
inference, respawn work, or treat a legacy PENDING row as evidence of success.

## Evidence and problem

`.agent/memory/issues-backlog.md` records that an independent reviewer accidentally ran
`aq-delegation-registry reconcile-pending --apply` in the canonical workspace, mutating 39 legacy rows.
The same record requires isolated-fixture tests and an explicit workspace-confirmation boundary. Existing
`TaskRegistry._with_inferred_status()` already supplies the bounded PID, fresh-heartbeat, and artifact
overlay needed for an evidence-based projection.

## Authority

| Fact | Authority | Result |
|---|---|---|
| Live task | TaskRegistry PID or fresh heartbeat overlay | Preserve `running` |
| Artifact terminal result | TaskRegistry artifact overlay with typed result | `done`, `failed`, or `cancelled` |
| Registry `done` / `completed` | Explicit non-empty `terminal_reason` | Preserve terminal status with reason |
| Missing / malformed / inconclusive authority | No completion authority | `stale` |

Every applied row receives a bounded `reconciliation_receipt`; HANDOFF gets an audit line. A second apply
has no candidate because only legacy `running` rows are examined.

## Operator contract

`aq-delegation-registry reconcile-pending` is dry-run by default. `--apply` requires the explicit,
non-interactive `--confirm-workspace` acknowledgement. This preserves autonomous authorized apply while
preventing accidental reviewer mutation. Tests patch the CLI module to temporary registry and repository
roots; no validation calls live apply.

## Exclusions

- No local inference, executor, dispatch, provider, service, or deployment changes.
- No PENDING/HANDOFF mutation during review or dry-run validation.
- No new lifecycle authority, daemon, dashboard, automatic scheduler, or M2A activation.
- No claim of independent acceptance, staging, commit, or deployment.

## Validation

- `python3 -m py_compile` on the three implementation/test surfaces.
- `python3 scripts/testing/test-local-delegation-artifact.py` exercises artifact, PID/heartbeat overlay,
  typed-terminal rejection, dry-run/default CLI, confirmation failure-before-mutation, confirmed isolated
  apply, receipts, and idempotence.
- `git diff --check`.
