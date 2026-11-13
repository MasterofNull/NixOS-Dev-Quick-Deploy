# P4 — Observable operation and exact-subject acceptance

DRAFT, 2026-11-12 UTC; pending independent design review. Accountable: factory/runtime maintainer and operator; evidence owner: runtime QA maintainer. Requirements R10–R12; depends on P1–P3 relevant paths accepted. Reuse aq-report, registered aq-qa integration checks, existing dashboard, model coordinator, approval control plane and PM tracker. No new dashboard framework, dispatcher, scheduler or cost service.

## Problem and intended behavior

Configuration, merged code and timer state do not prove a working factory. Local aq-report has no_data support but an earlier live JSON command was inconclusive (L04); one local Qwen slot and fallback/cost configuration do not prove measured routing (L05). Operators need the actual requirement/run/subject, current authority, outcome, health, spend and safe next action in one existing view. No-data and stale evidence must remain explicit. An inactive unit alone does not diagnose an outage.

## Three bounded slices

1. Wire existing event/receipt fields into aq-report and the dashboard: admitted/active/interrupted/quarantined/awaiting-review runs; requirement and exact subject; lease/reconciliation age; queue and operator intervention; learning eligibility; provider/token/runtime/retry cost completeness. Use observed counters and receipts, not generated healthy text. Costs distinguish measured, estimated and unavailable; record fallback and abandoned-attempt cost. Bound retention using existing policy.
2. Exercise operator journeys through existing controls: pause admission, cancel a bounded attempt, quarantine a receipt, inspect a stuck run, preview restart/reconcile and disable learning promotion. Actions require the existing actor authority and scope; worker/reviewer credentials cannot mint owner grants. Show pending, rejected and completed actions with immutable audit identity. Avoid showing internal implementation fields unless needed to decide what to do.
3. Run one reproducible exact-subject acceptance campaign after P1–P3 review. Reuse model eligibility evidence and capability-graduated routing. Select cheapest healthy model meeting task acceptance with a recorded spend/time ceiling; record dispatch-time lane availability (including quota exhaustion), capability evidence and each substitution with its reason. Escalation requires measured insufficiency or unavailability. Bind PM detection to real git/review/freeze/activation/blocker facts. Publish six-dimension attestation or a dated deferral per feature.

## Executable acceptance

A frozen finite manifest contains feasible success, eligible agent mistake, independently certified impossible spec, provider outage, missing dependency, operator cancellation, stale lease, duplicate delivery and forged authority. Run complete spec → delegate → isolated worktree/branch → test → independent exact-subject review → operator decision → observable outcome → learning decision. P1/P3 enforce feasibility/grader certification before admission and recertification after change; neutral outcomes neither penalize infrastructure nor reward abstention. Every attempted/retried task stays in raw evidence and denominators.

Pause during execution: no new tasks admitted; existing policy determines bounded active-task behavior and shows it. Cancel twice: one effective cancellation; reconcile twice after restart: no duplicate PR, training sample or external effect. Read-only reviewer cannot merge, activate or alter another branch; unauthorized operator calls have zero effect and leave audit evidence. Verify P2 path-boundary negatives and actual containment boundary separately. Parallel attempts cannot share test results or claim another attempt’s review.

Dashboard and aq-qa agree with the actual run receipts and process/workspace observations. Stop a producer or withhold receipts: state becomes stale/unknown within a frozen bound, never green. Restore it: state recovers without fabricated timestamps. Real integration CheckResult is registered in phases/__init__.py and ALL_PHASES alongside service/dashboard changes. Exercise an alert and its operator resolution; screenshots alone are insufficient. Record latency/throughput/cost using the same frozen task set and budgets as baseline; no invented numerical superiority threshold. Every discrepancy is evidence, not a reason to edit the fixture or hide a failed attempt.

Projection acceptance: without a genuine freeze/review/activation record, tracker cannot show that milestone accepted/active merely because documents or tests exist. A real blocker remains visible even after a commit. An exact-subject mismatch or revoked authority prevents activation. Evidence owner records hashes, actual command outputs, costs, intervention count and receipt reconciliation; independent runtime/UX reviewer repeats a representative success and failure journey. Documentation/source comparison cannot substitute for this live acceptance.

## Activation, control and rollback

Dated deferral 2026-11-12: proposed integrated/enabled/functionally validated/observable/intervenable/PM-live state is not verified. Factory/runtime maintainer owns next check after dependencies, exact-subject independent review and legitimate gates. Wave D/E merged recovery commits do not establish runtime activation. User-authorized work continues through required gates; no new blanket permission request is introduced by this draft.

Activation requires existing owner authority where required, with exact revision, intended services/features, six-dimension evidence and rollback owner recorded. Do not perform deployment or rollback as part of this documentation task. On unsafe state, operator pauses admission/promotion first. Owner uses approved deployment procedure to restore prior verified revision; preserve worktrees, receipts and raw observations for reconciliation. Validate restored reporting and real integration path before resuming. No hook bypass, synthetic pass, destructive cleanup or rewriting prior acceptance.

## Next session

After P1–P3 exact-subject acceptance, delegate telemetry adapters and fixture runs to measured-capable local Qwen, cross-component wiring to economical Codex, and runtime/UX acceptance to an independent eligible reviewer. Discover actual controls and signal paths before editing. Publish evidence and dated deferrals; do not call the factory complete until all shipped features satisfy the repository activation contract.
