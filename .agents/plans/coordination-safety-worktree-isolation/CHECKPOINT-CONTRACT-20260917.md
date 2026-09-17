# Checkpoint Contract — 2026-09-17 (Draft)

Status: preservation-only proposal. This document does not activate runtime
behavior, create a new registry, or change the lifecycle/acceptance authority.

## Compatibility boundary

The canonical authority remains `.agent/WORKFLOW-CANON.md`: its terminal
implementation dispositions are `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`,
`ACTIVATION_BLOCKED`, and `REJECTED`. A commit is not completion; Step 8.5
still requires integration, enablement, real-world validation, observability,
intervention where meaningful, and live PM tracking.

The protected `.githooks/commit-msg` hook remains authoritative on `main` and
`master`. It binds acceptance to independent PASS, non-author identity, and
the exact staged binary-patch SHA-256. Follow-up integration additionally
requires `Safe-At-Rest: true`, `Activation-Authority: false`, and `Next-Slice`.
`ACTIVATION_BLOCKED`, `REJECTED`, and provisional work remain isolated.

## Checkpoint meaning

`checkpointed` means evidence is preserved for later continuation, never that
the slice is accepted, complete, activated, or eligible for `main`. A holding
branch may contain further commits when the checkpoint is inert and records
full Tier-0 failures; it must make no accepted/main claim. A future
pre-commit preservation tier is proposed only, not implemented by this draft.

No `.agents/slices` directory or duplicate lifecycle registry is introduced.
The existing `.agents/plans/*/tracker.json`, task registry/PENDING records, and
event-projected `RESUME.json` remain the sources/projections already defined by
the repository.

A disposable worktree is only an assembly workspace. The durable branch/ref,
candidate hash, and synchronized task/tracker evidence retain the checkpoint
if temporary worktree metadata disappears. Losing that metadata does not imply
completion or authorize reconstruction without hash and scope revalidation.

## Record fields (in existing task/tracker records)

Use only the smallest bounded record:

`plan_id`, `slice_id`, `checkpoint_id`, branch/worktree, `base_commit`,
`candidate_subject_sha256`, disposition, `safe_at_rest`,
`activation_authority`, `next_gate_or_blocker`, validation evidence,
implementer/reviewer identities, and timestamp.

PM status and percentages are projected from ground truth; no manually typed
completion is valid. `paused` describes suspended activity and is never
terminal completion. `blocked` is non-runnable and non-complete. A checkpoint cannot override tracker
dependencies, lifecycle markers, review receipts, or activation grants.

## Pause and resume protocol

1. Before pausing, stop new mutations, record the exact branch/worktree,
   base/candidate hashes, disposition, changed-path ceiling, validation results,
   blocker/next gate, and retained artifact locations in the existing task
   record and resume event.
2. Mark the task `paused` (or `blocked` with a reason) only after the record is
   durably written; leave the holding branch intact. Do not merge, activate,
   rewrite history, or claim acceptance.
3. On resume, reload the task/tracker record and projected resume state; verify
   branch identity, base ancestry, changed paths, and candidate hash. Any
   mismatch invalidates prior review evidence and requires a fresh bounded
   review/validation.
4. Continue only when the recorded next gate is satisfied. Otherwise retain
   the artifacts and escalate; never infer completion from commit presence.

## Lightweight-model eligibility

Lightweight models may draft comments, commit-message prose, and checkpoint
facts only for exact bounded paths with deterministic Git/hash/schema checks.
One designated integrator applies staging/commit. Self-review is forbidden.
Use a stronger independent reviewer when authority, scope, hash lineage, or
conflicting evidence is uncertain. After one failed retry, stop automatic
retries and escalate with retained evidence to the designated
integrator/reviewer rather than widening scope.

Qualification is evaluated on: (1) path/scope adherence, (2) hash and schema
determinism, (3) truthful disposition/authority separation, (4) pause/resume
reproducibility, and (5) failure visibility. Outcomes are `QUALIFIED`,
`QUALIFIED_WITH_REVIEW`, or `NOT_QUALIFIED`; none grants activation.
