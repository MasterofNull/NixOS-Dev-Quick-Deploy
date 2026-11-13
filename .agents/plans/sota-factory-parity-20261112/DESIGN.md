# Software factory evidence and lifecycle parity

**DRAFT — pending independent design review.** Written 2026-11-12 UTC. No freeze, implementation acceptance or activation grant is asserted. This folder is a bounded integration plan, not a replacement platform. The [comparison report](../../../research_notes/Software%20factory%20SOTA%20comparison/REPORT.md) and its two source ledgers provide the research basis.

## Problem and intended behavior

The local harness has worktrees, delegation, review/gate machinery, telemetry and learning components. Supplied evidence does not demonstrate one authorized lifecycle connecting requirement, exact revision, attempt, reviewer, recovery, learning eligibility and live activation. A task should end with an inspectable receipt explaining what happened, why it may be accepted, whether it may inform learning and what remains inactive. Interrupted or impossible tasks must remain observable without being scored as agent mistakes.

External products document useful patterns rather than a comparable end-to-end winner. We adopt four: versioned tracker-driven work (Symphony), bounded isolated delegation (coding products and open factories), explicit interruption/reconciliation (durable runtimes), and visible human intervention (product control planes). We propose exceeding the inspected evidence set through independently authenticated learning eligibility and feasibility-neutral outcomes. That is a design goal, not a claim of superiority over uninspected features.

## Reuse and scope

Extend existing initiatives: `agent-agnostic-factory`, `coordination-safety-worktree-isolation`, `software-dev-factory-rollout`, `approval-control-plane`, the landed/deployed learning-attribution change #750 (`d7aa36d2f`; deployed system `60687d873`), and [phase184B](../phase184B-training-pipeline-prd.md). Existing accepted work stays accepted on its original subject; this plan adds only unproven integration contracts and tests. Confirm exact current paths/HEADs before editing. Do not implement another dispatcher, database, dashboard framework, training scheduler or approval system. Use existing stores and envelopes where they can enforce these contracts.

| Req | Existing mechanism on main | What is still missing |
|---|---|---|
| R02 review binds exact subject | `scripts/ai/aq-review-receipt` off-branch receipts on protected `review-receipts` branch; `review-disposition` required check on `pull_request_target` from trusted main; PR body `Reviewed-head-sha` + `Reviewed-subject-sha256` + non-author `Reviewed-by` | Link from receipt to requirement/attempt IDs; reviewer independence is lane-level, not identity-authenticated |
| R01 attempt/subject binding | `scripts/ai/aq-land` checkpoint (`.agents/delegation/outputs/aq-land/<branch>/checkpoint.json`: reviewed head, receipt key) | Requirement IDs, environment/model identity, outcome class |
| R04 claims/leases | `scripts/ai/aq-claim` (path claims with TTL + owner token) and `scripts/ai/aq-lease` | The review's historical observation was that the Claude lane had claimed its slices while Codex sessions had no claims; this resumed session now claims before edit. P2 should make claim-before-edit the contract rather than design a new lease |
| R10 visible unknown/stale state | Today's fixes: RSI convene seat states `delivered/short/down`; health-spider incidents auto-resolve with evidence when check passes again; payload audit reports quota exhaustion low after reset | A common "unknown vs stale vs clear" vocabulary across producers |
| R11 measured cost | `aq-payload-audit` now runs every 15 min in health monitor (status file + alert); delegate wrappers log per-lane quota errors | Actual token/time cost per attempt joined to outcome |
| R12 six-dimension activation | `config/activation-manifest.json` + `tier0.d/check-activation-manifest.sh`; `.agent/DEFINITION-OF-DONE.md` | Binding a manifest entry to attempt receipt |

The four PRDs are [P1 outcome evidence](P1-outcome-evidence.md), [P2 recovery and execution boundaries](P2-recovery-isolation.md), [P3 learning promotion](P3-learning-provenance.md), and [P4 operational acceptance](P4-operational-acceptance.md). The user has authorized this work; design authorship does not satisfy the required independent scope freeze or legitimate delivery gates. Resolve those prerequisites before implementation proceeds.

## Requirement and source map

IDs below are stable across the four PRDs. CF/RT/EV/L references resolve in the [coding ledger](../../../research_notes/Software%20factory%20SOTA%20comparison/coding-factories.md) and [runtime/local ledger](../../../research_notes/Software%20factory%20SOTA%20comparison/runtime-and-local-evidence.md). Sources motivate requirements; they do not prove local acceptance.

| Requirement | Contract | Evidence/motivation | Owning PRD |
|---|---|---|---|
| R01 | Bind requirement, attempt, exact subject/environment and evidence hashes | CF-15; RT-01; L03 | P1 |
| R02 | Independent authorized review binds exact immutable subject | CF-11; local review policy | P1 |
| R03 | Independently certify feasibility/grader before admission, recertify changes, and separate neutral outcomes from eligible agent error at every sink | L06, L07, L09 | P1, P3 |
| R04 | Reconcile bounded leases/claims after interruption without silently duplicating work | CF-01, CF-09, CF-15; RT-03, RT-06 | P2 |
| R05 | Idempotent handback and explicit external-effect reconciliation | CF-09, CF-15; RT-06 | P2 |
| R06 | Fail closed on ambiguous write scope; distinguish worktree from OS containment | CF-02, CF-08; L02 | P2 |
| R07 | Preserve memory/source identity, trust and tenant provenance | CF-10; L07, L09; L08 stays in the separate producer backlog | P3 |
| R08 | Authenticate independent eligibility receipts at ingest, capture/flush and steering | L06, L09 | P3 |
| R09 | Held-out measured benefit/regression gate before learning promotion | EV-01, EV-02; L07 | P3 |
| R10 | Visible unknown/stale state and bounded operator intervention | CF-05, CF-07; RT-05; L01, L04 | P4 |
| R11 | Cheapest eligible routing uses measured capability and total actual cost | CF-06, CF-08; L05 | P4 |
| R12 | Activation requires six-dimension evidence and reversible control | L01, L03, L04; local Definition of Done | P4 |

## Shared contracts and authority

Reuse an existing versioned envelope if possible. Required logical fields: schema version, requirement IDs, run/attempt IDs, subject commit plus dirty-tree digest where relevant, input/artifact hashes, environment/tool/model identity, producer identity, observed UTC interval, outcome class, feasibility evidence, linked review receipt, cost completeness and activation subject. A receipt is evidence, not permission to merge/deploy/train. Hashes establish identity; authenticated issuer authority and independence establish eligibility.

Outcome classes include eligible agent error, successful result, short/partial answer, infeasible requirement, infrastructure/provider interruption, operator cancellation and unknown. A short/partial answer is distinct from an infrastructure interruption and does not become adverse learning without independently authorized eligibility. A positive or negative learning decision additionally requires an independently authorized receipt scoped to the exact attempt and subject. Unknown, missing, mismatched, stale or unauthenticated provenance is retained in raw storage and quarantined from training and steering. A caller's `good_output`, `success` or `reviewed` flag cannot grant eligibility. Review and activation remain distinct authorities. Reviewers cannot accept their own implementation or mint owner grants.

Transitions are explicit: admitted → running → evidence pending → reviewed → activation eligible, with interrupted/quarantined/deferred branches. This is a logical projection over existing records, not a mandate for a new state-machine service. Resume reconstructs from durable authority and reconciles process/workspace reality. The supervisor cannot assume a lost reply means an unperformed side effect. A reviewer rejection or infrastructure failure preserves evidence and records a bounded next action.

## Delivery order and economical roles

| Order | Bounded work | Dependencies | Accountable role and cheapest eligible execution |
|---|---|---|---|
| 0 | Independently review this exact document set; resolve hook-composition prerequisite | **BLOCKED:** missing factory install/run evidence and unsupported native/precommit composition | Codex owns the hook-composition prerequisite; fresh independent architecture/failure/UX/security reviewer |
| 1 | Finish L09 attribution sink repair and P1 receipt compatibility | #750 baseline (`d7aa36d2f`); first repair is `sync_feedback_corrections_to_gaps` at `interaction_tracker.py:272`; supported hooks | Claude acknowledged ownership of the L09 repair in the catch-up queue; its implementation is in review, not accepted or landed. Measured-capable local Qwen may support inventory/fixtures; independent reviewer |
| 2 | P2 recovery and scope edge cases | P1 identity/outcome contract | Economical Codex implementer; local Qwen bounded reproduction; separate runtime reviewer |
| 3 | P3 eligibility propagation and phase184B promotion journey | P1 accepted; P2 identity/recovery semantics where capture spans restart | Economical Codex for trust boundary; local Qwen fixture assembly; independent provenance reviewer |
| 4 | P4 live acceptance and cost/operator journey | P1–P3 relevant paths accepted | Local Qwen for known telemetry adapters if measured eligible; economical Codex for cross-component wiring; independent runtime/UX review |

Eligibility must be measured for the slice, not inferred from provider branding. Record selected role/model, lane availability (including quota exhaustion), capability evidence, reason, cost ceiling and any substitution with its reason at dispatch. A flagship reviews integration or resolves demonstrated complexity; it does not silently become the default implementer. Parallelize read-only inventories and independent fixtures after contract freeze; serialize shared producer changes and activation.

Each PRD has at most three slices. A slice ships service, registered aq-qa integration check and live dashboard state together or in consecutive commits, per repository contract. No dormant scaffolding gets counted as delivery. Existing attribution review is a prerequisite, not evidence that its 44 reported tests establish full safety: the negative-feedback-to-hints sink remains an identified gap.

## Shared acceptance and non-gaming rules

Freeze a finite fixture manifest before running: feasible coding success, genuine agent mistake, impossible/conflicting specification, provider outage, missing dependency, cancellation, duplicate delivery, stale lease and malformed authority. Store fixture hashes and expected class independent of the worker. Use real integration dependencies in final E2E; simulations establish failure behavior only. Report all attempts, retries, human interventions, unresolved cases and denominator exclusions. Impossible/infra/cancelled/unknown cases must not improve success denominators or become adverse agent learning.

Never edit tests, timestamps, source-health flags or receipt fields to manufacture acceptance. The independent evaluator owns expected outcomes and cannot share implementation authority. Compare baseline and candidate on identical held-out tasks, environment, model, token/time budgets and retry limits; disclose contamination and uncertainty. A negative or inconclusive result remains valid evidence, not a reason to silently change the task set. Security/authority tests have zero tolerated unauthorized promotions or effects. Performance thresholds are frozen from baseline before candidate evaluation.

For activation, require exact-subject evidence that each feature is integrated, enabled, functionally validated, observable, intervenable and PM-tracked; otherwise a dated deferral names owner, missing evidence and next check. A merged commit is not an activation grant. Dashboard unknown is an honest state, never a synthetic pass. No source inspection or unit suite alone establishes live readiness.

## Controls, rollback and evidence

Operators can pause admission, cancel a bounded attempt, quarantine a receipt and disable promotion while retaining raw evidence. Resume/retry/reconciliation actions preview their subject and authority. Network/secrets stay scoped to existing policy. OS containment, when required, uses the existing declarative Nix security boundary and separate activation evidence; worktree routing alone is insufficient.

Rollback stops admission/promotion first and preserves raw records, claims and evidence. Revert via the existing approved deployment workflow; agents do not perform owner-gated destructive rollback. Replay only after compatibility and effect reconciliation. No wholesale data deletion or rewriting prior accepted history. Feature flags/control names must be discovered in implementation and recorded in acceptance evidence, not invented here.

Evidence belongs under `docs/harness-first/evidence/<date>-sota-factory-<slice>.md`, linked to exact hashes, command outputs, test manifest, receipts and operator actions. This bundle ships with the first P1 code PR; it is not a standalone docs-only PR. `tracker.json` is editorial: dependencies, goals and detection signals only; state is projected from git/freeze/review/activation truth. There is intentionally no acceptance claim or freeze record in this draft. The hook-composition prerequisite is owned by Codex and is **BLOCKED** on unsupported native/precommit composition and missing composed real-Git traversal evidence. Existing preflight already requires direct gate-run evidence; that requirement is not the missing producer behavior. Current retrofit cannot compose existing hooks; approved rollout §4.2 defers manager composition. The completed independent review returned REQUEST_REVISION: receipt-aware doctor, immutable offline dependencies, common-gitdir transaction locking, linked-worktree ownership, semantic deduplication/order and real-Git traversal evidence remain unresolved. Revise and independently review the exact subject before an opt-in extension preserving every existing hook can be used. It is not readiness evidence and no hook or pre-commit bypass is acceptable.

Independent feasibility and grader certification precedes admission. Changed task, environment or grader invalidates that certificate and requires recertification. A worker’s impossible-task claim cannot exempt an otherwise eligible failure; neutral attribution never earns reward for abstention. Independently verified eligible agent mistakes remain learning signals. Anthropic’s 2026 vulnerable-environment experiments motivate this requirement but establish no local causality or complete anti-hacking guarantee.

Dated deferral, 2026-11-12 UTC: P1–P4 integration, enablement, real E2E, observability, intervention and live PM evidence remain pending exact-subject independent review and legitimate delivery gates. Accountable owner: factory design lead coordinating each PRD owner. Next check: the frozen-document review, then prerequisite receipts; this draft is not an activation claim.
