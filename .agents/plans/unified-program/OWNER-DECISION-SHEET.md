# Owner Decision Sheet — Unified Program (Q1–Q10)

**For**: hyperd. **Prepared**: 2026-07-13 by claude-fable-5. **Subject commit**: `aa2e4452`.
**How to use**: each decision below has a recommendation and an exact activation statement.
Approve by saying/pasting the statement (edit freely); every approval is recorded in the round
and takes effect only after the round's lane reviews are aggregated (codex folds in 2026-07-15).
You may decide any item early — owner authorization is distinct from lane consensus and both are
recorded.

**Decision update (2026-07-18):** Q1 and Q2 are ratified against the exact historical subjects in
`Q1-Q2-OWNER-RATIFICATION-20260718.md`. This sheet is now a post-ratification projection and therefore
has a different digest from the decision inputs; it grants no implementation authority.

| Q | Decision | Recommendation | Why (one line) |
|---|----------|----------------|----------------|
| Q1 | Synthesis = parent architecture (with UNIFIED-PROGRAM-PLAN §3/§4 as its execution projection) | **RATIFIED 2026-07-18** against synthesis `00c7dbc5…` and plan `2cab0bdd…` | Parent architecture is decided; the plan remains a non-authoritative projection |
| Q2 | First shadow state vertical authority hypothesis | **RATIFIED 2026-07-18**: workflow-run-task legacy-live/Postgres-shadow at B2-D0 commit `c11bf7a1`; migration owner `hyperd`; historical PRD §9 frozen | Only B2-C1 authorization preparation and independent review are unblocked; implementation and writes remain unauthorized |
| Q3 | Security model: principal attestations + CapabilityLease, no fail-open; eight network profiles | **APPROVE direction now, ratify profile list at Foundation C planning** | Direction is uncontested across all corpora; exact profiles deserve their own threat pass |
| Q4 | Fable behavior contract → model-neutral versioned canon policy | **APPROVE** | Behavior is sound; naming it per-model ages badly; content unchanged |
| Q5 | Measured, expiring lane-eligibility registry (roles model-neutral) | **APPROVE**; seed rows: codex=orch/impl/review, opus=bounded impl, antigravity=research/review (impl-INELIGIBLE until promoted), local=measured envelope | Replaces vendor defaults with evidence; VF-8 feeds it; synthesis §11 shows why named defaults are wrong |
| Q6 | Kernel front door: keep `local-orchestrator` vs named revision toward `aq` | **KEEP for now**; revisit as a named revision when Product F CLI work starts | No benefit to deciding early; frozen surface stays frozen |
| Q7 | Eval factory = universal promotion gate | **APPROVE as principle**; mechanics land in Product E | Uncontested across all four corpora |
| Q8 | Adjudicate ten Cycle-0 authority rows (target, transition owner, deadline, rollback each) | **DECIDED 2026-07-18**: 10/10 owner targets projected as `ADJUDICATED`; observed physical condition remains `SPLIT_BRAIN` | Foundation A owner gate is satisfied without falsely claiming writer convergence |
| Q9 | Activate VF Track V | **REVIEW AMENDED CONTRACTS, THEN AUTHORIZE PER SLICE** | Aggregate requested revision; VF-1/VF-3 authority and L2B sequencing now have explicit prerequisites |
| Q10 | Rebudget measured 27 GB inference envelope | **MEASURE FIRST** — choose resident small model, speculative decoding, both only if proven, or defer to fleet hardware | Avoid assuming one quant step funds two concurrent capabilities without RAM/VRAM/latency evidence |

## Activation statements (paste any you approve)

- Q1: **DECIDED** — see `Q1-Q2-OWNER-RATIFICATION-20260718.md`.
- Q2: **DECIDED** — see `Q1-Q2-OWNER-RATIFICATION-20260718.md`; no implementation authority was granted.
- Q3: "I approve the zero-trust security direction (principals + leases, no fail-open); network-profile list to be ratified at Foundation C planning."
- Q4: "I approve converting the Fable parity contract into a model-neutral versioned canon behavior policy."
- Q5: "I ratify the measured expiring lane-eligibility registry with the seed rows as recommended."
- Q6: "Kernel front door stays local-orchestrator; any change requires a named kernel revision."
- Q7: "I approve eval-gated promotion as the universal change mechanism, mechanics to land in Product E."
- Q8: **DECIDED** — see `../aqos-refoundation-cycle0/FOUNDATION-A-OWNER-ADJUDICATION-20260718.md`.
- Q9: "Return the amended VF contracts for bounded review; activation will be issued per exact slice after prerequisites pass."
- Q10: "Measure the 27 GB resident/speculation alternatives on target hardware before I choose one, both, or fleet deferral."

## Standing waiting-on list (auto-checked at round aggregation)

1. local (Qwen) review file — dispatched 2026-07-13, 7200s window, round OPEN for late fold.
2. antigravity review file — inbox dropped, IDE lane live.
3. codex review file — lane returns **2026-07-15**; re-dispatch check:
   `aq-collab-round status --round unified-program` (re-dispatch if its 07-13 dispatch errored).
4. Q8 owner-session evidence retained in the Foundation A authority record.
5. Q1/Q2 ratification recorded; prepare and independently review a hash-bound B2-C1 authorization.
6. Aggregation → AGGREGATE.md → PRD amendments → subject re-binding → PREPARED_ONLY
   implementation authorizations per track (VF fast slices first: VF-7, VF-1).
