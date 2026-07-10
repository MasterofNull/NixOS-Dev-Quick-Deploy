# AQ-OS Refoundation Cycle 0 — Provisional Aggregate

**Status:** `REQUEST_REVISION` — implementation is not authorized.  
**Updated:** 2026-07-10T04:55:00Z
**Owner brief:** `.agents/prompts/AQOS_OWNER_NEXT_CYCLE_META_PROMPT.md`

**Current planning package:** `PACKAGE-ROOT.json`
**External SHA-256:** `0a2b0cce9876edf9b58d627c8c2d59608996f9e8c98d5b7e8fba8f7d065bdb3f`
This superseding package incorporates independent Anthropic/Gemini amendments and is ready for fresh
exact-root review; it is not ratified or authorized.

## Evidence status

| Lane | Artifact/state | Substantive | Counts for model-diverse quorum |
|---|---|---:|---:|
| Claude slot | `claude.md`, explicitly Codex-orchestrator proxy | yes | no |
| Codex | `codex.md`, recovered from independent internal team after headless stdin failure | yes | one Codex-family lane |
| Local/Qwen | failed after 2,233.4 s and four tool calls; empty output after transient switchboard refusal | no | no; failure evidence only |
| Anthropic/Fable 5 | `REVIEW-FABLE5.md`, `APPROVE_WITH_CHANGES` on predecessor/review-pin bytes | yes | independent findings; zero approval for current root |
| Antigravity/Gemini | `antigravity-findings-review.md`, `APPROVE_WITH_CHANGES` on root `2b905b24…` | yes | independent findings; conditional verdict approves nothing |
| Independent internal teams | three read-only proposals; two adversarial cross-reviews | yes | review evidence, not distinct model quorum |

The headless Codex and local failures remain evidence only. Anthropic and Gemini reviews are genuinely
independent, but both are conditional and their accepted amendments create a new subject root; neither
is converted into current approval.

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

## Revision package completed

The revised package now contains:

1. full product critique, clean-sheet intent, 12-row parity matrix and ranked gaps;
2. canonical object lifecycle hypotheses and exact planning decision transitions/cascades;
3. safe proposed owner/quorum defaults, exact canonical bytes and commit protocol;
4. evidence algebra, required-claim matrix and immutable QA/pointer semantics;
5. complete threat register with delivery cycles, owners and restoration assertions;
6. machine/human evidence manifests and an externally hashed package root;
7. frozen C0.2 consumers, exact integration check IDs and existing operator surfaces;
8. honest split-brain authority discovery states and a Cycle 1 ADR output path;
9. external reference/build-adopt comparison, six-cycle migration and consolidation candidates;
10. three slices bounded by validation, resource, rollback, retirement and stop contracts.

## Remaining ratification blockers

1. Owner acceptance of authorization, quorum, waiver, proxy and critical-human policies.
2. Formal closure/waiver of failed local and unverified Antigravity lanes without approval weight.
3. Two genuinely independent model-family/principal reviews of the current package root.
4. Measured C0.2 thresholds, telemetry roots, retention owner and privacy/GC acceptance.
5. Hashed implementer/reviewer agreement on inter-slice contracts.
6. Explicit per-file ownership and no-overlap preflight before any implementation authorization.
7. The read-only C0.3 scan now proves broad split-brain and exact candidate paths; target adjudication,
   owners and deadlines remain Cycle 0 work.

## Provisional Cycle 0 dependency contract

| Slice | Produces | Consumed by | Gate |
|---|---|---|---|
| C0.1 | typed decisions, exact evidence/reason codes, cascades and assignment invariant | C0.2, C0.3 | invalid rounds block; positive authorization works exactly once; recovery preserves corrupt bytes |
| C0.2 | evidence algebra, required claims and immutable QA provenance | C0.3 | missing/invalid/conflicting evidence cannot pass; concurrent artifacts survive |
| C0.3 | observed claims/writers, contested-state adjudication and Cycle 1 ADR | Cycle 1 plan | every writer/reader/bypass/owner/deadline enumerated; no invented singleton authority |

No slice is delegated until the integration contracts are acknowledged against exact hashes, the
package is independently reviewed, the plan is ratified and owner authorization is explicit.

## Provisional verdict

`VERDICT: REQUEST_REVISION — the revised package is coherent and review-ready, but the live false lock,
failed local lane, unverified Antigravity lane, missing model diversity, unratified owner policy,
unmeasured thresholds and unsigned ownership/contracts block ratification and all implementation.`
