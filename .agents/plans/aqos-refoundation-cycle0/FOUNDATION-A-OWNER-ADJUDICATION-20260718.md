# Foundation A Owner Adjudication — Ten Authority Targets

Status: `OWNER_DIRECTION_RECORDED — PENDING RE-REVIEW AND CONTRACT PROJECTION`
Decision ID: `foundation-a-authority-targets-20260718`
Decision date: 2026-07-18 UTC
Adjudicator: repository owner (`hyperd`)
Scope: Q8 mechanical authority targets only

## Decision basis

The owner directed the agent team to complete the gating tasks needed to unlock the refactor and
supplied the drafted target for each of the ten C0.3 authority conflicts. This record preserves that
direction before mutation of `config/system-state-authorities.yaml`.

The current schema cannot yet represent a selected target while truthfully retaining an observed
`SPLIT_BRAIN` condition. Therefore this record does not change any observed condition, claim physical
convergence, authorize Cycle 1, or itself unblock Foundation B2. The accepted Foundation A contract
slice must land first; then these decisions are projected into the registry with provenance,
transition owner, deadline, and rollback boundary.

## Adjudicated targets

| Authority row | Adjudicated logical target |
|---|---|
| `planning-round` | One versioned `RoundState` / `round.json` manifest mutation boundary. Dispatch logs, agent contributions, aggregate documents, and status views are evidence or projections and carry no independent authorization weight. |
| `delegation-lifecycle` | One host/coordinator dispatch-broker mutation boundary using `TaskRegistry` under its canonical lock/CAS contract. Provider wrappers and `aq-agent-reap` cease to be independent writers/reconcilers after measured migration. |
| `intent-resume` | Separate typed Intent Lock authority from delegation lifecycle. One `aq-event` append authority owns continuity events; `PENDING`, `RESUME`, and `PULSE` are rebuildable projections with no direct writers after migration. |
| `workflow-run-task` | The hybrid coordinator owns workflow/run/task state transitions. Legacy coordinator JSON remains live during the first shadow vertical; a Postgres outbox/CAS path is shadow-only until separate evidence and cutover authority. Retire standalone/sync writers after parity. |
| `qa-effectiveness` | Immutable C0.2 QA invocation evidence plus one versioned scorecard reducer is authoritative. Latest pointers, reports, and dashboard views are projections; competing score calculators and clobber writers retire after parity. |
| `routing-model-execution` | The coordinator owns canonical route decisions (`ResolvedRunPlan`); switchboard is the sole model-generation execution gateway. Direct llama/eval generation bypasses retire after measured parity. “Sole gateway” does not transfer route-decision authority from coordinator to switchboard. |
| `learning-eval` | One coordinator-owned, versioned `EvaluationRun` / `PromotionDecision` ledger governs eval and promotion. Loop JSONL, spools, checkpoints, corpora, and artifacts retain lineage as evidence/CAS content, not competing promotion authority. |
| `memory-rag` | `MemoryBroker` is the sole mutation gateway, backed by a typed durable fact/lineage log; Qdrant collections are rebuildable projections. Direct Qdrant writers migrate behind broker/collection ownership and then retire. |
| `configuration` | Nix options through evaluated systemd environment into typed Python consumers form the durable configuration authority. Dashboard configuration is read-only/proposal projection; process-local `_CONFIG`, aliases, and undeclared overrides are not durable authority. |
| `dashboard-operator` | A coordinator-owned typed `ApprovalStore` is authoritative and may reuse the existing SQLite `ContextStore` as its physical store. In-memory approval dictionaries retire; dashboard and audit-chain surfaces are projections/evidence. SQLite reuse does not grant arbitrary dashboard code independent authority. |

## Transition defaults

- Transition owner: `hyperd` is the concrete accountable transition owner for all ten rows until a
  later owner-signed decision delegates a row. A service or role label alone does not replace this
  assignment.
- Resolution deadline: retain the existing 2026-10-09 deadline unless a row-specific reviewed plan
  sets an earlier date.
- Rollback: disable the new shadow writer/reader and preserve immutable evidence; never restore
  competing live writers merely to roll back a projection or cutover.
- Physical convergence: remains future Cycle-1 implementation. Every row stays observed
  `SPLIT_BRAIN` until source-verified writer retirement proves otherwise.
- First B2 candidate: `workflow-run-task`, with coordinator logical authority and Postgres
  outbox/CAS as a shadow physical hypothesis only. No writes start until the exact vertical design,
  authority hypothesis, and authorization pass independent review.

## Per-row rollback boundaries

Every boundary below is owner-attributable, decision-bearing, and keeps one authority during
rollback. Rollback owner is `hyperd` for every row.

| Authority row | Measurable trigger | Bounded rollback action | Singular authority during rollback |
|---|---|---|---|
| `planning-round` | Any schema/CAS invariant failure or nonzero replay mismatch between `RoundState` and its projections. | Stop the failing projection/adapter, preserve its evidence, and rebuild it from the last accepted `round.json`; do not re-enable document writers. | Versioned `RoundState` / `round.json` mutation boundary. |
| `delegation-lifecycle` | Missing durable admission receipt, CAS violation, or registry replay mismatch greater than zero. | Park new admissions, disable the failing broker adapter, preserve receipts, and reconcile only through the canonical registry boundary. | `TaskRegistry` under the host/coordinator broker lock and CAS contract. |
| `intent-resume` | Missing/duplicate continuity event or any mismatch rebuilding `PENDING`, `RESUME`, or `PULSE`. | Stop the failing projector, retain the append log, and rebuild projections; do not restore direct projection writers. | Typed Intent Lock plus the single `aq-event` append authority. |
| `workflow-run-task` | Any shadow outbox/CAS parity mismatch, duplicate transition, or dropped transition. | Disable Postgres shadow reads/writes, retain shadow evidence, and continue the existing coordinator state path; do not cut over. | Hybrid coordinator with legacy coordinator JSON during the shadow vertical. |
| `qa-effectiveness` | Any scorecard replay mismatch or missing invocation-evidence digest. | Stop publishing the candidate reducer output and recompute from immutable evidence with the last accepted reducer version. | Immutable QA invocation evidence plus the last accepted versioned scorecard reducer. |
| `routing-model-execution` | Any `ResolvedRunPlan`/executed-model mismatch, unreceipted generation, or direct-gateway bypass. | Park the affected route, disable the failing adapter/bypass, and replay only from the accepted plan through switchboard. | Coordinator `ResolvedRunPlan` for routing and switchboard for generation execution. |
| `learning-eval` | Any non-reproducible evaluation digest, promotion replay mismatch, or unlinked artifact. | Freeze new promotions, preserve candidate evidence, and recompute from the last accepted ledger version. | Coordinator-owned `EvaluationRun` / `PromotionDecision` ledger. |
| `memory-rag` | Any missing lineage entry, unauthorized direct collection write, or broker/Qdrant replay mismatch. | Disable the failing projection writer, preserve the durable lineage log, and rebuild Qdrant through `MemoryBroker`. | `MemoryBroker` plus its typed durable fact/lineage log. |
| `configuration` | Any evaluated-value/type mismatch between Nix, systemd environment, and typed Python consumer. | Reject the candidate proposal/override and restore the last accepted evaluated configuration generation; do not write dashboard-local config. | Evaluated Nix -> systemd environment -> typed Python configuration chain. |
| `dashboard-operator` | Any approval CAS conflict, missing audit link, or mismatch between API response and durable approval record. | Freeze new approvals, preserve the audit chain, and serve the last accepted durable record read-only until repaired. | Coordinator-owned typed `ApprovalStore` backed by its approved `ContextStore` physical store. |

## Exclusions and remaining owner decisions

This adjudication does not ratify Q1, approve the final Foundation-C network-profile list, select a
Product-D/E RAM strategy under Q10, activate Track V broadly, authorize a new lifecycle store, or
permit live traffic cutover. Those decisions retain their separate gates.

The quarantined Antigravity collector remains inert and unexecuted. Its archival move is a separate
evidence-hygiene slice because active accepted records currently reference its rejected path.

`RECORD: owner direction for all ten Foundation-A logical targets; projection awaits the accepted adjudication contract.`
