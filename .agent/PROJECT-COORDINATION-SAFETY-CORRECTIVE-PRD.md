# CS-1F1 — safe isolation failure and durable handback

## Evidence and objective

Owner appointed Codex orchestrator. Independent non-author audit of landed
e8a905e8 (exact diff8c96ce92b5024387b33262209c309302f6604e7b5795f56288653492ddbaf0f5)
found failed staging can return handback success then force-remove uncaptured edits.
Paths/branches are not verified and isolation failure resumes shared writers.
Preserve landed history; correct these concrete invariants before mutating dispatch.

## Scope / minimal-code

Reuse the existing worktree helper and wrappers; no new lifecycle/lease authority.
Implementer owns scripts/ai/lib/worktree-isolation.sh, delegate-to-codex,
delegate-to-local and scripts/testing/test-worktree-isolation.py. Root may integrate
QA registration in existing phase0.py/_aq-qa-bash after fixture is frozen. No
dispatch.py or model/payload edits. Preserve foreground empty-answer guard.

## Frozen acceptance criteria

- Validate task identifiers, canonical paths, registered worktree and expected
  delegate/task branch before any staging, commit or teardown; reject shared
  checkout, other lane, symlink/path escape and mismatched branch.
- Editing dispatch cannot silently fall back to shared checkout when isolation
  creation fails. Explicit shared editing must fail closed until separately
  validated integration authority exists; read-only operations remain compatible.
- Handback success requires complete binary/full-index diff export and private
  commit evidence verified after successful staging. Include already committed
  agent edits relative to the dispatch base, not only current staged edits.
  Partial export/stage/commit failure returns failure and retains every artifact.
- Remove forced teardown/prune. Preserve worktrees on all failures. Default
  retention is acceptable; cleanup is separately authorized, never presumed from
  successful generation. No new external credential or bypass of review/hooks.
- Hermetic fixture proves creation/staging/export/commit failure, wrong path or
  branch, committed+uncommitted binary/new/deleted files, foreground/background
  caller failure propagation and shared-index preservation. No real remote agent
  execution or deletion of existing user worktrees.
- Register existing QA integration path for the fixture, and retain operator
  failure visibility through existing wrapper task status/audit and monitor.
  Explicitly defer richer retained-worktree UI to CS-4; no claim of live activation.
- Syntax, fixture, independent exact-subject review and stable staged Tier-0
  precede atomic commit. One corrective batch; follow-up nonblockers queue forward.

## Security / authority / rollback

Source changes are owner-authorized continuation; deletion, forced worktree
removal, branch switching, push, deployment and protected manifest exceptions
are not granted. Tests use isolated temporary repos only. Rollback is a separately
authorized revert; never erase private branches/patches. CS-2 lane parity and CS-3
integration lease follow this slice, not competing unreviewed implementations.

## Disposition

PLAN_READY_WITH_FOLLOWUPS: root source assessment and independent audit establish
the critical batch. Claude same-baseline planning is running; Gemini advisory and
local catch-up are queued. Local is not inference-ready after its measured timeout;
do not block preservation repairs on absent contributions or fabricate consensus.
