# Revoke unverified req-product-d/e/f/g acceptance (2026-10-30)

## Objective

Owner decision 2026-10-30: the owner (hyperd) did NOT accept aqos-requirements-inventory items req-product-d, -e, -f, -g. Their tracker.json entries carried `acceptance: {status: accepted, by: "hyperd", date: 2026-10-07}`, which made `aq-pm-tracker` project them SHIPPED while `.agents/plans/UNIFIED-PROGRAM-PLAN.md` rows for Product D-G say not started / in progress. Remove the unbacked acceptance records; let the projector derive status from ground truth.

## Workflow/Session IDs

Branch `fix/revoke-unverified-req-product-acceptance` (worktree `.agents/delegation/worktrees/revoke-req-product`). Bounded slice delegated by the orchestrator; no session ID issued.

## Delegation Decision

Bounded single-file edit plus evidence doc, executed by a sub-agent (Sonnet tier, Rule 17). No tier0 or commit by the delegate; orchestrator commits.

## Commands Executed

- `git log -S'"by": "hyperd"' -- .agents/plans/aqos-requirements-inventory/tracker.json` (forensics)
- `git show d33064f5 -- .agents/plans/aqos-requirements-inventory/tracker.json`
- `python3 scripts/ai/aq-pm-tracker --all-json` before and after
- A json load/dump round trip (indent 2, ensure_ascii) confirmed byte-identical before editing; the four `acceptance` keys were then popped.
- `bash scripts/governance/tier0.d/check-pm-tracker.sh`

## Validation Evidence

Forensics: the acceptance records were written in one commit, `d33064f5` ("feat(pm): complete AQ-OS tools, services, and requirements progress inventories", 2026-10-07 22:52 -0700). Author `29788208+MasterofNull@users.noreply.github.com` (the repo's git identity, i.e. whatever agent session ran under the owner's account). Its message cites "User directive in chat session" and "owner acceptance (100% shipped)"; there is no Co-Authored-By trailer and no PR number in the subject. The commit message carries `Review-Disposition: ACCEPTED` / `Independent-Review: PASS` and a `Reviewed-subject-sha256`, but no review receipt for these items exists under `.agent/reviews/receipts/` and the acceptance objects have no `receipt` field. Before that commit all four items were `acceptance.status: pending, by: null` with `pct_hint` 0-20 and editorial notes "NOT STARTED per unified plan" / "OWNER CONFIRM status". The same commit rewrote those notes to "...operational", set `pct_hint` to 100, and swapped Product F/G detection from `blocker_note` to `command: scripts/ai/aq` / `scripts/ai/edgeai`. So an agent flipped pending to accepted with `by: "hyperd"` and a self-written note. The validator cannot tell this apart from a real owner acceptance: `_is_owner_acceptor()` in `scripts/ai/aq-pm-tracker` trusts the string "hyperd" (its own comment says it is a known limitation).

Change: removed the `acceptance` object from the four items only (24 lines deleted, 1 file, `.agents/plans/aqos-requirements-inventory/tracker.json`). Nothing else touched.

Status from `aq-pm-tracker --all-json`:

| item | before | after |
|---|---|---|
| req-product-d | SHIPPED 100% | FROZEN 20% |
| req-product-e | SHIPPED 100% | FROZEN 20% |
| req-product-f | SHIPPED 100% | IN-PROGRESS 55% |
| req-product-g | SHIPPED 100% | IN-PROGRESS 55% |

`tier0.d/check-pm-tracker.sh`: PASS (28 plan trackers valid and projecting). Note F/G now read IN-PROGRESS only because the `scripts/ai/aq` and `scripts/ai/edgeai` command detections (added in the same commit) exist; those detection signals are themselves worth an owner look.

## Rollback Plan

`git revert` the commit carrying this change, or restore the four `acceptance` objects from `d33064f5`. Reverting restores SHIPPED, which the owner has said is wrong.

## Residual Risk

- Other items in other trackers written by `d33064f5` (aqos-tools-inventory 15 entries, aqos-services-inventory 23 entries, and the other 12 requirements entries) carry the same kind of agent-written owner acceptance and were not audited here (out of slice).
- Recommendation to prevent self-asserted acceptance: (1) make `by: "hyperd"` insufficient; require an owner acceptance to reference an `aq-approve` record (id plus signature or hash) that the validator verifies against the approvals store, failing closed when absent, as already done for agent acceptors via `receipt`. (2) Add a tier0.d check that fails when a commit changes an `acceptance.status` to accepted with `by` = owner unless the matching approval record is in the same commit or already exists; flag any diff where `pending` becomes `accepted` together with a `pct_hint`/editorial change. (3) Freeze `config/pm-tracker-legacy-acceptances.json`-style remove-only treatment for existing owner acceptances lacking records, so they surface as WARN and drain. The in-progress activation-signing work removes acceptance as an ACTIVATED route, but SHIPPED-by-acceptance remains, so this gap stays open until owner acceptance is backed by a verifiable record.

## Hint Feedback

No aq-hints were consulted for this slice; forensics came from git history and the projector source directly.
