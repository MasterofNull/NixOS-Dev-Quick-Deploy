# Delivery loop simplification: design

Status: PLAN_READY_WITH_FOLLOWUPS (2026-11-06). Lead: Claude (orchestrator).
Inputs: `brief.md`, `codex.md`, `gemini.md`, RSI incident 77b562e768f2aa63d6a9a592, backlog FACTORY-DELIVERY-LOOP-TOO-HEAVY and RSI-CANNOT-TRIGGER-EXPERT-ROUNDS.

## Round record

| Seat | Result |
|---|---|
| Codex | Delivered `codex.md` |
| Gemini (headless, replacing the retired Antigravity seat) | Delivered `gemini.md` |
| Local Qwen | Did not deliver. It stopped after a planning step without writing its file. Dispatched at 18:28 on 2026-11-05 with the task inlined. Scaffolding follow-up in S5 |
| Claude | This synthesis |

This is not unanimous expert sign-off: two independent seats plus the lead. The lead's own draft proposal was attacked and partly withdrawn.

## Decisions

1. **No merge queue.** Withdrawn. Both seats reject it: a queue tests a merged tree no reviewer saw, and it breaks head-bound review. This repo is user-owned, and GitHub offers merge queues to organization-owned repos. Serialized landing plus CI on the merge ref covers the need.
2. **Receipts leave the PR branch.** The largest waste is changing the subject to record its review. Receipts move to a dedicated append-only `review-receipts` branch. Pushing there starts no PR CI and leaves the head unchanged.
3. **Not tree-hash receipts as proposed.** Gemini's slice 1 assumes a receipt commit keeps the tree hash. Adding a file changes the root tree, and rebasing onto a moved main changes it too. Bind to exact commit and tree together, in the off-branch record.
4. **Not raw commit statuses as the trust root.** Every lane shares the owner's `gh` token, so a status is forgeable. Codex's point also stands: committed receipts are not forgery-proof today, and `aq-review-receipt` calls itself detection-grade. So this design is **detection-grade, no stronger than today, and says so**. A separate issuer identity is the upgrade path (see Owner decisions).
5. **Disposition reads live state.** `check-review-disposition.py` fetches current PR metadata and the receipt at run time, not the frozen event payload. That removes the push/edit race, and re-running the check starts to work.
6. **Gate placement by criteria, not by wholesale move.** Codex's caution wins over Gemini's sub-10-second target: live checks need a representative environment, so moving them blindly to hosted CI would lose evidence.
7. **`aq-update` extends `aq-deploy-current`.** On demand, not scheduled: the owner wants the refresh immediately before a rebuild. Gemini's `--ff-only` is rejected because this repo squash-merges.
8. **Not built:** scheduler, custom merge queue, general workflow engine, automatic conflict resolver, emergency force-merge flag.

## Frozen MVP slices

### S1. Off-branch review receipts + live disposition
Receipt binds repo, PR, head commit, tree, base commit, policy version, reviewer run id, output digest, author lane and verdict. Written to `review-receipts`; the required check reads it live.
Accept: receipt issue leaves the head unchanged and reruns only review-disposition. Rejected: self-review, invented run, mismatched output, replay onto another head, stale head. A same-second push and edit gives the correct final result. Old PRs with committed receipts still validate during migration.

### S2. Gate placement
- **Local tier0 `--pre-commit`:** deterministic, offline, bounded, relevant to staged content (syntax, secrets, schemas, changed policy and contracts). Must not time out at load average 15.
- **Pre-push:** push safety only; no repeat of CI suites.
- **CI:** exhaustive test inventory, job completeness, fake-gate detection, lock and closure validation.
- **Pre-deploy and scheduled monitor:** live-state checks (0.16.2, 0.1.2, 0.10.66), in an environment that can run them.
Accept: a receipt-only or doc-only commit passes tier0 with the live stack down. Seeded regressions in `test-tier0d-gate-mutation.py` are still caught, each at the stage named for it. 0.10.66 stops raising a false HIGH under the health-monitor sandbox.

### S3. `aq-land` in the repo
Merge main (stop on conflict), independent review of that exact head, push, PR, receipt, wait for checks, merge. One lane at a time, reviews included, because they execute tests locally. State lives in git refs and a checkpoint under `.agents/`, never `/tmp`. Replaces `.agents/delegation/outputs/landing/land.sh`.
Accept: main moves during landing, and stale evidence is rejected. Kill after push, after PR creation, after receipt and after merge: each re-run resumes without duplicates. Conflicts stop and report, never auto-resolve. The stuck `repo-structure-lint` status case (job concluded, check in progress) is handled.

### S4. `aq-update`
Detect Nix-affecting changes since the deployed revision. If there are none: sync only, no rebuild. If there are: refresh every input in a worktree, verify with CI's exact commands and flag any unlocked node, land the lock through S3, sync, deploy (one sudo prompt), refresh the MCP baseline from a verified clean revision, validate, and write a ledger outside the checkout.
Accept: no Nix delta means no rebuild. An unlockable input blocks with a named reason. Main moving mid-run is handled. Replaces `main-checkout-sync-20261104.sh`. Covers the on-demand half of recovery item P1.9.

### S5. RSI convenes expert rounds
`prsi-orchestrator` opens `aq-collab-round` when an incident is: repeated 3 or more times in 7 days; or high severity and design-class; or its fix touches a gate, trunk protection or review authority. Limits: at most 1 open round, 2 per day; design only, no code changes; seats from the role matrix; one lead; result is a `DESIGN.md` plus a tracker. Owner gets a one-line notice, and an owner decision only when one exists.
Local seat scaffolding: inline the task, ask one narrow question, and write the file for it from its reply.
Accept: a seeded repeat incident opens exactly one round. A second trigger in the budget window queues instead. A down seat is recorded and the round continues. Implemented after S1 to S4, so it runs on a stable loop.

## Failure modes
- **Lane down:** next eligible independent reviewer, recorded; otherwise wait.
- **CI outage:** wait; never reuse a stale green.
- **Power loss:** reconcile from checkpoints and remote state.
- **Owner offline:** landing continues; deployment stays pending.

## Measures (baseline: PRs #685 to #705)
Reviewed-to-merged time (median, P95), CI runs per subject, local gate latency, owner actions per rebuild, false reds, stale-review rejections, unique defects caught per gate, recovery success. Simpler means fewer actions and reruns with zero escapes across the seeded regression corpus.

## Owner decisions
- **Later, optional:** a separate GitHub App identity for issuing review checks, which is what would make review non-forgeable rather than detectable. It requires the owner to create the App. S1 is built so this can be added.
- **None needed now.** Merge queue is withdrawn.

## Open question
`strict` required checks stay off: strict would re-run CI whenever main moves. S3 reviews after merging main, and CI tests the merge ref. Revisit if a semantic conflict escapes.
