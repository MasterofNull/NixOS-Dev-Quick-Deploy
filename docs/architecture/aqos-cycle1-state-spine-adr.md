# ADR: AQ-OS Cycle 1 State Spine (proposal)

**Status:** Proposed — Cycle 1 decision draft. **NOT authorized.** This ADR is a
proposal produced by Cycle 0 slice C0.3 discovery. It does **not** authorize any storage
migration, new writer, service, route, or database change. Implementation requires a
separate, explicit Cycle 1 authorization under `OWNER-POLICY-RATIFICATION.md`.
**Slice:** C0.3 (Authority, projection, bypass & retirement ledger).
**Discovery SSOT:** `config/system-state-authorities.yaml` (schema
`config/schemas/system-state-authorities.schema.json`), checker
`scripts/governance/check-state-authorities.py`.
**Cycle 1 authority:** `NOT_AUTHORIZED`.

## Context

C0.3 inventoried who currently owns each critical cross-system state and what its target
disposition should be **before** Cycle 1 moves durable truth. The bounded read-only checker
reports every one of the ten inventoried authorities as `SPLIT_BRAIN`: multiple writers or
adjudicators claim authority for the same state with no single monotonic revision. The full
per-row evidence (observed writers with `file:line`, bypasses, projections and their rebuild
sources, shims, adjudicator/recovery owners, target hypotheses, and resolution deadlines)
lives in the registry SSOT; this ADR summarizes the decision those rows feed. Every non-`SINGLE`
condition blocks C0.3 ratification until an adjudicated target disposition and deadline exist,
so the ratification of C0.3 and the authorization of any Cycle 1 move remain future, gated steps.

Representative divergences the ledger records:

- **planning-round** — `round.json` manifest vs. dispatch log vs. per-agent Markdown/JSON
  sidecars vs. lane-status quorum authorization (fail-open legacy fallback).
- **delegation-lifecycle** — `TaskRegistry` under lock vs. direct provider-script writes vs.
  `aq-agent-reap` as a second reconciler bypassing the common lock.
- **intent-resume** — `PENDING` overloaded as manual Intent Lock and delegation `in_flight`;
  RESUME/PULSE declared as event projections yet written directly; recovery boundary UNOWNED.
- **workflow-run-task** — coordinator lock vs. standalone executor vs. `sync-workflow-sessions.py`
  writing the same file; Postgres checkpoint recovery UNKNOWN/unwired.
- **qa-effectiveness**, **routing-model-execution**, **learning-eval**, **memory-rag**,
  **configuration**, **dashboard-operator** — each carries an analogous split between an
  intended single authority and one or more bypass writers or mtime/volatile adjudicators.

## Decision (proposed, not authorized)

For each authority, Cycle 1 should converge on the **single owner named as that row's
`target_hypothesis`**, demote every other writer/cache/sidecar to a **projection with a declared
rebuild source**, and place a **compatibility shim** — with an owner, use/divergence telemetry,
and a deadline — over any writer that cannot be retired in the same change. No convenient
singleton is asserted where the ledger records `SPLIT_BRAIN`/`UNKNOWN`/`UNOWNED`; the target
hypotheses are candidates that Cycle 1 must adjudicate and independently review before any code
moves durable truth.

Proposed spine shape (to be decided in Cycle 1, not here):

1. One durable writer per authority behind one lock/CAS boundary, emitting a monotonic revision.
2. All readers become projections that can be rebuilt from the durable source (the registry
   already names each projection's rebuild source).
3. Bypass writers are either routed through the owner or shimmed with telemetry + a deadline;
   compatibility expires after two clean release cycles or 90 days, whichever is first.
4. `UNKNOWN`/`UNOWNED` recovery boundaries (e.g. PENDING recovery, workflow checkpoint recovery,
   dashboard approval recovery) get an assigned owner before any migration, never a silent default.

## Options considered

- **A — Per-authority consolidation behind existing owners (proposed default).** Lowest blast
  radius; each row's target hypothesis is realized independently with its own shim/telemetry/
  deadline. Preserves the current substrate; no new store required to begin.
- **B — Single unified state store (e.g. one relational spine) for all ten authorities.** Strong
  global ordering, but a large simultaneous migration, broad blast radius, and a new durable
  dependency — out of scope for this ADR and explicitly not authorized.
- **C — Status quo + monitoring only.** Rejected as a target: the ledger's whole purpose is to
  end SPLIT_BRAIN before Cycle 1 moves durable truth; monitoring alone leaves divergence writable.

## Consequences

- C0.3 discovery is complete and observable, but C0.3 **ratification** stays blocked until each
  `SPLIT_BRAIN` row has an adjudicated target disposition and deadline.
- Cycle 1 work must carry its own authorization; this ADR grants none. A clean cycle means no
  divergence, no fallback write, successful replay/restore, and verified zero legacy writes.
- The bounded checker remains read-only for the whole of Cycle 0: it never enforces runtime
  behavior, adds a writer/route/service, or migrates storage.

## Rollback

This ADR is a document; "rollback" is withdrawal or revision of the proposal. Incorrect registry
declarations are corrected by reviewed new registry revisions or reverted as source. If checker
CI registration is noisy, only the CI registration is rolled back while the reviewed findings are
retained.

## Open questions for Cycle 1

1. Is Option A (per-authority) sufficient, or do cross-authority invariants force a shared spine?
2. Who owns each currently `UNKNOWN`/`UNOWNED` recovery boundary?
3. What durable revision/ordering primitive backs each converged owner?
4. What use/divergence telemetry threshold licenses retiring each compatibility shim?
