# Foundation B2-C1 authorization review

**Review date:** 2026-07-18  
**Reviewer:** Codex sub-agent `/root/b2_c1_authorization_review`  
**Role:** independent read-only architecture, security, SRE, privacy, and concurrency reviewer  
**Review type:** exact-subject implementation-authorization gate; no implementation acceptance  
**Final verdict:** **PASS**

## Exact subject

| File | SHA-256 |
|---|---|
| `.agents/plans/aqos-foundation-b2/B2-C1-IMPLEMENTATION-AUTHORIZATION.md` | `db657588b7d256ad2c518958b2875cc1fa46eea6955421043930d9c62bdc5093` |

Any content change invalidates this verdict. The reviewed record is explicitly `PREPARED_ONLY`; this
review does not activate it or authorize implementation.

## Evidence inspected

- The exact authorization subject above.
- The Q1/Q2 owner ratification record and its independent `PASS` review.
- The current Codex-Fable synthesis, Unified Program Plan, and owner-decision projections.
- The accepted Foundation B2 ADR, post-ratification PRD projection, D0 design packet, and exact D0
  independent `PASS` review.
- `config/workflow-blueprints.json`, including an independent enumeration of its phase identifiers.
- The three proposed shared implementation files and the absence state of all five proposed new files.
- The generated governance/testing wiki and Understand-Anything graph status for the affected Phase-0
  and focused-test surfaces. Graph conclusions were treated as advisory and verified against files.

## Provenance and inventory verification

All nine bound design/projection hashes, the read-only blueprint hash, and all three shared-file
predecessor hashes match the authorization exactly. Commit
`cf3e81d7a09205ad808c1b5db8a113ba297eff0d` resolves as a Git commit and contains the ratified Q1/Q2
projection chain. The five proposed new implementation paths are absent.

The authorization freezes exactly eight implementation files: five new files and three modified
shared files. Together with the authorization and this review, that is the D0 maximum ten-file B2-C1
planning ceiling. A ninth implementation change is a mandatory stop. The blueprint remains read-only
at `12ba465a5ede653579ac52752558ed9068fe0bbfd407dbc44cb2b80b70c72374`.

The historical D0 review remains represented accurately: it passed the historical ADR/PRD/design
bytes for owner adjudication. The authorization separately binds the current post-ratification PRD
projection and does not imply that the D0 reviewer reviewed those changed bytes.

## Architecture, security, privacy, SRE, and concurrency findings

1. **Contract boundary — PASS.** The grant requires exactly five independently versioned Draft
   2020-12 variants: event, snapshot, immutable outbox, delivery control, and health. Every object
   boundary is closed, versions are variant-specific, extension bags are forbidden, and unknown or
   cross-variant versions reject.
2. **Canonical form — PASS.** One pure UTF-8 JSON rule requires NFC normalization, lexicographically
   sorted keys, insignificant-whitespace removal, deterministic process-independent bytes/digests,
   bounded non-negative JSON integers, and rejection of booleans-as-integers, floats, non-finite
   values, and numeric strings. Accepted event bytes are capped at 2 KiB.
3. **Opaque phase registry — PASS.** Independent enumeration of the frozen blueprint found 56 phase
   occurrences and exactly 14 unique identifiers: `assign`, `commit`, `decide`, `delegate`,
   `discover`, `execute`, `intake`, `learn`, `plan`, `prd`, `propose`, `scope_lock`, `validate`, and
   `verify`. The grant requires complete, unique, collision-free, stable, domain-separated opaque
   mappings; unknown, duplicate, colliding, free-form, or model-derived values reject. Raw identifiers
   are limited to reviewed registry keys and adversarial test inputs and are prohibited from every
   produced surface.
4. **Pure mapper — PASS.** The module must be standard-library-only, import-side-effect-free, begin
   from an empty output object, perform no I/O, and expose only pure validation, mapping,
   canonicalization, receipt-order, capacity, and decision functions. It cannot persist, enqueue,
   deliver, retry, sleep, create a task/thread/worker, or repair history.
5. **Decision completeness — PASS.** The authorization freezes all seven mutually distinguishable
   outcomes: first insert, expected-revision advance, exact idempotent replay, gap, stale receipt,
   identity/digest collision, and nonidentical post-terminal conflict. It requires monotonic
   `revision = expected_revision + 1`, terminal uniqueness, no fabricated repair/renumbering, and
   capacity vectors at 0, 64, and 65. More than 64 pending receipts must return `parked`; no queue is
   created.
6. **Privacy evidence — PASS.** The mandatory canaries cover objectives, queries, prompts, phase
   notes, outputs, tool inputs/results, agent messages, secrets, paths, environments, isolation data,
   lesson references, extensions, raw phase IDs, model phase text, and hashed/encoded forbidden phase
   text. Rejection must precede serialization, and forbidden values must be absent from accepted
   bytes, digests, errors, fixture outputs, and health outputs.
7. **Test and CI boundary — PASS.** Golden fixtures must cover five variants, canonical stability,
   every phase token, every decision branch, size/capacity boundaries, terminal uniqueness, and
   independent-version rejection. The focused offline test consumes—not duplicates—the fixture and
   scans for prohibited imports and side effects. Phase-0, `_aq-qa-bash`, and the validation registry
   may execute only this fixture-backed oracle; candidate acceptance additionally requires focused
   tests, compilation, JSON/schema validation, `aq-qa 0 --machine`, and Tier-0.
8. **Health truthfulness — PASS.** The only permitted fixture health claim is
   `authority=legacy_json_authoritative`, `coverage.aq_qa=ready`, and
   `coverage.web_dashboard=not_wired`. Operational health, service observation, dashboard parity,
   Postgres authority, writer convergence, and measured runtime budgets remain blocked until B2-O1.
9. **Resource envelope — PASS.** The applicable 2 KiB event and 64-receipt ceilings are frozen and
   may only tighten. The C1 oracle cannot represent future latency, connection, RSS, disk, retention,
   lag, parity, or trial ceilings as measured health and cannot relax any Q2-frozen PRD section 9
   value.
10. **Negative authority — PASS.** Mandatory stops comprehensively prohibit database/SQL/ORM/client,
    connection, DDL, migration, credentials, reads/writes, storage, runtime hooks, services, Nix/env,
    dashboard/API, filesystem state writes, network/socket/port, process/subprocess, thread/task/worker,
    traffic, activation, deployment, cutover, store integration, raw phase output, extensions,
    resource relaxation, cleanup, rollback, predecessor drift, shared-file conflict, blueprint edits,
    and a ninth implementation file.
11. **Role separation — PASS.** Exactly one bounded implementer owns all eight files and cannot
    delegate, stage, commit, deploy, activate, or accept its own work. A different session must review
    the exact candidate hashes; any reviewer edit recuses that reviewer. Only the orchestrator may
    integrate after exact-hash `PASS` and all validations.
12. **Activation discipline — PASS.** This review leaves the record `PREPARED_ONLY`. Activation must
    be a later explicit owner record naming this exact authorization hash, one implementer, a timestamp,
    and an expiry no longer than 24 hours. The authorization is single-use and consumed only by the
    first complete exact eight-file candidate report. Later slices remain separately unauthorized.

## Threat-model conclusion

The slice is structurally incapable of creating a live state authority if implemented within its
ceiling: no database, runtime, service, state-write, process, worker, network, dashboard, or traffic
surface is available. The highest residual risks—privacy leakage through phase material, replay
misclassification, canonical nondeterminism, queue growth, false operational-health claims, and scope
expansion—are each converted into explicit golden vectors, acceptance evidence, or mandatory stops.
Any discovered need to cross one of those boundaries requires a new hash-bound amendment and a new
independent review.

No implementation, staging, commit, DDL, connection, write, runtime hook, service, deployment,
traffic, cutover, cleanup, rollback, delegation, or self-review action was performed.

`VERDICT: PASS — the exact PREPARED_ONLY authorization faithfully binds B2-C1 to an eight-file pure-contract oracle; implementation remains unauthorized pending explicit hash-bound owner activation.`
