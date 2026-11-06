# Independent design: delivery-loop-simplification

## Findings

The largest waste is changing the subject to record its review, followed by duplicated validation. Remove those causes before adding orchestration.

`scripts/ai/aq-review-receipt` explicitly describes detection-grade evidence under a shared Unix identity. `scripts/governance/check-review-disposition.py` checks receipt structure and declarations, but its CI path does not independently authenticate the reviewer run. A committed receipt is therefore not non-forgeable either. Checks are easier to replace silently unless their evidence has durable, independently controlled retention. Hashing a fabricated statement does not authenticate it.

The disposition check reads the event snapshot; fetch current PR metadata instead, then recheck the head before publishing a result. Prefer structured receipt data over PR-body declarations.

`scripts/governance/tier0-validation-gate.sh`, `.githooks/pre-push`, and `config/ci-checks.json` overlap. Separate proof obligations from execution locations. Live checks need an isolated, representative environment or the owner’s deployment target; moving them blindly into hosted CI loses evidence.

`scripts/maintenance/aq-deploy-current` already supplies checkout synchronization, preflight, revision verification, and deployment. Extend it. The named `.agents/delegation/outputs/landing/land.sh` was absent from this checkout, so its implementation was not assessed. `.agents/plans/system-integrity-recovery/DESIGN.md` supports retaining independent review, complete test execution, and anti-tautology checks.

## Recommended design and risks

Bind review to repository, PR, exact commit, tree, base commit, policy version, reviewer run, output digest, author identity, and verdict. An issuer must observe the independent run and retain its output; it must not merely sign caller-supplied assertions. Keep issuer credentials outside the shared account/host trust boundary. Require that issuer’s GitHub App as the check source; retain an append-only external issuance/revocation log and reconcile it against merges. Shared owner credentials cannot forge that App identity, but owner bypass remains a trust root and must be disabled or explicitly audited. [GitHub supports expected check sources](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

Defer merge queue. One required aggregate check is sufficient only if it fails on missing, skipped, cancelled, or failed expected jobs and verifies test inventory. Queue eligibility depends on repository ownership/plan; queue checks run on a new merged subject, require `merge_group`, and conflicts can still eject entries. A reviewed PR head is not approval of that merged tree. Queue adoption must preserve exact-subject review or explicitly redesign that proof. [GitHub queue contract](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).

## Frozen MVP slices and acceptance

1. **Receipt channel.** Replace receipt commits with isolated issuer checks and durable evidence. Metadata changes rerun only disposition verification. Acceptance: reject self-review, invented runs, mismatched outputs, replay, stale head/base, and owner-token check spoofing; issuing a receipt leaves the Git head unchanged. Issuer isolation is a prerequisite, not a claim supplied by a signature.

2. **Gate placement.** Keep local checks deterministic, offline, bounded, and relevant to staged content: syntax, secrets, schemas, and changed policy/contracts. Pre-push retains push safety; remove repeated suites. CI owns exhaustive test inventory, job completeness, fake-gate detection, and lock/closure validation. Isolated integration and deployment checks retain their appropriate environments. Acceptance: replay every supplied regression class; each has a named enforcing gate and fails there, including live-state mutation. Measure local latency under load before setting the budget.

3. **Durable landing.** Put `aq-land` in the repository with atomic external checkpoints and remote-state reconciliation. Serialize landings; require server-enforced current-base checks and renewed review after subject changes. Never resolve conflicts automatically. Acceptance: move main during landing; reject stale evidence. Kill after push, PR creation, receipt, and merge; resume without duplicate actions or lost evidence. No scratch-script dependency.

4. **Owner update.** Extend `aq-deploy-current`: detect NixOS-affecting changes since the deployed revision, refresh the lock immediately before rebuilding through the normal PR gates, synchronize all current updates, pin the deployment revision, validate, and persist its ledger outside the checkout. Acceptance: no NixOS delta means no rebuild; unlockable input blocks; concurrent main movement is reported as pending; deployment verifies state-directory writers after activation.

Lane down: use another eligible independent reviewer or wait. CI outage: wait, never reuse stale green. Power loss: reconcile checkpoints. Owner offline: deployment remains pending. Build no scheduler, custom merge queue, generalized workflow engine, or automatic conflict resolver.

Compare against PRs #685–702: median/P95 reviewed-to-merged time, CI executions per subject, local latency, owner actions, false reds, stale-review rejections, unique defects per gate, and recovery success. Simplicity requires fewer actions/reruns with zero escapes across the seeded regression corpus.
