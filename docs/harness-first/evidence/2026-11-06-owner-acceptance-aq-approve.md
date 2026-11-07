## Objective
Recovery item P0.7: an acceptance with `by: hyperd` must be backed by a real aq-approve record. Most of the gate already existed (`approval_ref`, hash binding, frozen remove-only allowlist, pinned baseline, `--check-owner-acceptance`). This change closes the remaining gaps only.

## Workflow/Session IDs
Branch feat/pm-tracker-aq-approve, worktree `.agents/delegation/worktrees/p07-approve`. Date 2026-11-06. Staged, not committed.

## Delegation Decision
Implementer: Claude Sonnet 5.5 sub-agent (Rule 17, balanced tier). Did not edit `scripts/governance/tier0.d/check-pm-tracker.sh` (fix/gates-placement changes it); all changes are in `aq-pm-tracker`, `aq-approve` and tests.

## The gap
1. The verifier checked that a record named the plan/item/hash and was approved, but never checked it came through an owner door. A hand-written JSON with `decision: approved` and any `door`/`resolved_by` (or none) passed. Now the record must carry `door` in {chat, terminal, dashboard}, `resolved_by` equal to the owner seat (`<user>:owner`, what `aq-approve approve` stamps), and an `alert_id` (`attn-<16 hex>`) equal to its file name.
2. Nothing produced a record: no `tracker_acceptance` executor in aq-approve and no record writer, so the "aq-approve then tracker acceptance" flow did not exist end to end. Added the validate-only `tracker_acceptance` executor and `aq-pm-tracker --record-acceptance <attn-id>`, a host-side writer that refuses unless the attention archive shows the alert approved by the owner seat AND the inbox audit log shows an approve line with an owner door, for the current acceptance hash. It writes the record and the decision-log line in the worktree and prints the `approval_ref`; it never edits tracker.json and refuses to overwrite.
3. An unreadable record raised a traceback instead of a clean failure; now a reported error (fail closed).

Already enforced before this change (kept, regression tests added): missing approval_ref fails; allowlisted legacy passes; allowlist cannot grow.

## What CI can and cannot verify
CI checks out the repo only. The aq-approve stores (`.agents/attention/ATTENTION_ARCHIVE.jsonl`, `/var/lib/nixos-ai-stack/optimizer/prsi/approval-inbox-audit.jsonl`) are local, so CI cannot read them. CI enforces: the committed record exists, is byte-bound to `approval_ref.sha256`, names this plan/item/acceptance hash, has an owner door and owner-seat actor, is append-only against the merge-base, and the allowlist is frozen and remove-only. The host-side cross-check against the archive/audit runs only in `--record-acceptance` at mint time. Limit: both stores and the record are same-uid files, so a process running as the owner's user can forge all of them; this is evidence of a decision, not authentication (assurance stays `recorded`, never `signed`; the signed path is slice 3). A forged record is a visible PR diff needing independent review.

## Request producer (addendum)
`aq-pm-tracker --request-acceptance <plan-dir> <item-id>` pushes one `pm-acceptance` attention alert (plan, item, acceptance hash, goal, validation goal, detection evidence), deduplicated by (plan, item, hash). It refuses an item with no proposed owner acceptance block, one that already has an approval_ref, and one that does not project SHIPPED (evidence/activation signal/test missing). It never writes an acceptance.

## Owner commands: accept one item
The agent drafts the acceptance block `{status: accepted, by: hyperd, date, note}` (no approval_ref) in the item in a slice worktree, then:
1. Agent: `python3 /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/aq-pm-tracker --request-acceptance <plan-dir> <item-id>` (run from the worktree)
2. Owner: `aq-approve` (note the number N and the tag T), optionally `aq-approve show attn-<id>`
3. Owner: `aq-approve approve N --tag T --door chat`
4. Agent, in the slice worktree: `python3 scripts/ai/aq-pm-tracker --record-acceptance attn-<id>` (prints the approval_ref JSON), paste it as `approval_ref` in the item's acceptance block
5. Agent: `python3 scripts/ai/aq-pm-tracker <plan-dir> --check`, then commit the record, LOG.jsonl and tracker.json together.

## Commands Executed
- `python3 scripts/testing/test-pm-tracker-owner-acceptance.py`
- Same new tests against HEAD versions of aq-pm-tracker and aq-approve.
- `python3 scripts/ai/aq-pm-tracker .agents/plans/system-integrity-recovery --check`
- `python3 scripts/ai/aq-pm-tracker --check-owner-acceptance --baseline-sha256 <pin>`
- `scripts/governance/tier0.d/check-ci-test-coverage.sh`

## Validation Evidence
- test-pm-tracker-owner-acceptance.py: `Ran 66 tests in 80.569s` / `OK` (MintFlow now starts from `--request-acceptance` through the real aq-approve CLI)
- Request-producer tests against the pre-producer code: `FAILED (failures=3)` (flow, dedupe, refuse-not-ready).
- Against old code: `FAILED (failures=2, errors=6)`: door/actor/alert-id, agent-written, unreadable-store, and all five MintFlow tests fail. The GateAllowlistGrowth tests pass on old code (existing behavior, now pinned).
- aq-pm-tracker --check (system-integrity-recovery): `PASS: system-integrity-recovery/tracker.json valid + projects`
- --check-owner-acceptance: `[owner-acceptance] PASS: allowlist 131 unbacked owner acceptance(s) (remove-only vs baseline/merge-base/tip); every owner acceptance backed; records append-only`
- check-ci-test-coverage.sh: `[tier0.d/check-ci-test-coverage] PASS (759 tests: 609 declared, 150 exempt)`

## Rollback Plan
Revert the three scripts and this file. No data migration; no records exist yet.

## Residual Risk
- The offline/full split in check-pm-tracker.sh (fix/gates-placement) is not covered; `check_owner_acceptance` fetches origin and fails closed offline, unchanged here.
- No live `aq-approve` run against the real stores; the flow is proven with throwaway stores via env overrides.
- One item at a time only: no scheduled queue generator and no bulk acceptance (design slice 2 is not built).
