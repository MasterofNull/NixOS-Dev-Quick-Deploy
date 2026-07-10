# AQ-OS Refoundation Cycle 0 — Provisional Aggregate

**Status:** `REQUEST_REVISION` — implementation is not authorized.  
**Updated:** 2026-07-10T04:25:00Z  
**Owner brief:** `.agents/prompts/AQOS_OWNER_NEXT_CYCLE_META_PROMPT.md`

## Evidence status

| Lane | Artifact/state | Substantive | Counts for model-diverse quorum |
|---|---|---:|---:|
| Claude slot | `claude.md`, explicitly Codex-orchestrator proxy | yes | no |
| Codex | `codex.md`, recovered from independent internal team after headless stdin failure | yes | one Codex-family lane |
| Local/Qwen | original agent lane alive with fresh heartbeat; no artifact yet | pending | pending |
| Antigravity/Gemini | inbox issued; no artifact yet | pending/unavailable | no |
| Independent internal teams | three read-only proposals; two adversarial cross-reviews | yes | review evidence, not distinct model quorum |

The headless Codex failure, local retry, and Antigravity absence remain part of the evidence;
none is converted into an approval by status inference.

## Machine-state invalidity reproduced live

`aq-collab-round collect --round aqos-refoundation-cycle0` transitioned the round to
`CONSENSUS_LOCKED` with:

- verdict tally `ABSTAIN: 3`;
- `contributions={}`;
- `aggregate_path=null` and `aggregate_hash=null`;
- local still reported `local-running-or-unparsed`;
- Antigravity reported no output;
- both substantive artifacts under provisional `REQUEST_REVISION` cross-review.

Therefore the machine lock is **invalid evidence**. Human/orchestrator truth for this round is
`REQUEST_REVISION`; no assignment or implementation may derive authority from `round.json`.
This is the real-world reproduction and primary acceptance fixture for C0.1.

## Convergence

All substantive proposals and three independent internal teams converge on:

1. AQ-OS is a local-first NixOS control plane for bounded, replayable, operator-governed
   agent work; it is not an AGI persona or feature-maximization product.
2. The four planes remain an explanatory/operator model, not four state authorities.
3. Target shape: modular coordinator/control plane; Postgres state+event/outbox hypothesis;
   Redis rebuildable coordination; Qdrant semantic projection; local filesystem CAS;
   switchboard as generation gateway; one API for CLI/console; NixOS substrate.
4. Exactly three Cycle 0 concerns precede durable-kernel implementation:
   - C0.1 evidence-bound consensus/review truth;
   - C0.2 truthful evidence and effectiveness semantics;
   - C0.3 authority, duplicate-path, and retirement inventory.
5. No Cycle 0 service, Postgres migration, new broker, SPA, NATS, Temporal, SPIRE,
   small-resident model deployment, or portability claim.
6. JSONL, PULSE/RESUME, registry/sidecars, Markdown consensus, and dashboard caches become
   named projections after migration; they are not peer authorities.

## Required revisions before PRD ratification

1. Await or formally close local and Antigravity lanes. A status-only or failed output is an
   abstention/training signal, never agreement.
2. Treat Claude proxy and recovered Codex proposal as one model family for quorum.
3. Add the complete 12-hypothesis parity matrix, canonical object model, current authority/
   dependency map, weighted scores, and decision log to the consolidated PRD.
4. Cover all 12 owner threats with prevention, detection, intervention, and recovery tests.
5. Add an evidence manifest: commit, timestamp, command/source, artifact hash, freshness,
   evidence class, and environment limitations.
6. Separate `direction_ratified`, `plan_ratified`, and `implementation_authorized` states.
7. Define `substantive contribution`, accepted verdict policy, trusted producer attribution,
   canonical bytes/hash algorithm, amendment resolution, and operator recovery actions.
8. Bound every slice by exact files or discovery outputs, validators, exit/status contracts,
   APU/token/runtime/disk/cardinality budgets, rollback, and same-cycle retirement.
9. Keep destructive/crash/replay tests isolated from live PULSE/RESUME, latest QA artifacts,
   registries, and production Postgres.
10. Treat Postgres+outbox as a strong Cycle 1 hypothesis pending C0.3 cost, failure, restore,
    and migration evidence—not as Cycle 0 implementation authority.

## Provisional Cycle 0 dependency contract

| Slice | Produces | Consumed by | Gate |
|---|---|---|---|
| C0.1 | typed evidence/reason codes and valid direction/plan states | C0.2, C0.3 | invalid AQ-OS v1 and this round replay truthfully |
| C0.2 | evidence/status algebra and current broken-producer inventory | C0.3 | live no-data/failed-validation cannot false-pass |
| C0.3 | ratified authority/retirement map and Cycle 1 ADR inputs | Cycle 1 plan | all writers/readers/bypasses/rollback owners enumerated |

No slice is delegated until this table is expanded into mutually reviewed integration
contracts and the consolidated plan is ratified.

## Provisional verdict

`VERDICT: REQUEST_REVISION — direction converges, but the live ABSTAIN-only false lock,
non-independent proxy lanes, pending local/Antigravity evidence, incomplete owner deliverables,
and missing operator/resource contracts block PRD ratification and all implementation.`
