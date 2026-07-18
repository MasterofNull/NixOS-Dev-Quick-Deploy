# Foundation B2-D0 independent design review — revision 2

**Reviewer:** Codex recovery reviewer (`foundation_b2_design_review_recovery`)  
**Role:** independent architecture / security / SRE / concurrency reviewer  
**Date:** 2026-07-18  
**Review type:** exact-subject design gate; no implementation acceptance

## Exact revised subject

| File | SHA-256 |
|---|---|
| `.agents/plans/aqos-foundation-b2/WORKFLOW-SHADOW-ADR.md` | `1bf65352993d5496ca5f3f6d8d1aea9078ac9f21427464cda6a6360523ee02bb` |
| `.agents/plans/aqos-foundation-b2/WORKFLOW-SHADOW-PRD.md` | `1496651ee11f20a82e953098489d866937ceb21d8cbda68553d5c18ea1b709c4` |
| `.agents/plans/aqos-foundation-b2/B2-D0-DESIGN-PACKET.md` | `d8a0f368ea45bae47180aa73ba654af846941da8e98a682155729f94cd839d81` |

Any change to those files invalidates this verdict.

## Evidence inspected

- The exact revised three-file subject above.
- `config/system-state-authorities.yaml` @ `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a`.
- `.agents/plans/UNIFIED-PROGRAM-PLAN.md` @ `2cab0bdd2f560052f315a14be1b64b4e173cee7b4239dcac3e582af815924ac2`.
- `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` @ `66744ec9efd08604dd58c86e6f864bf5a11d5c82707a2081914964a84d02b467`.
- The cited coordinator handler, standalone executor, synchronization writer, and separate checkpoint
  topology from the revision-1 review.
- Revision-1 review @ `f1f4c115d9872616a16328472a1d2e138ebf6dda955db57c0ec1dc9173e750bc`.
- `reviewer-gate`, `security-audit`, and `testing-patterns` skill contracts.

## Prior-finding closure

1. **Legacy durability — CLOSED.** ADR §§3.1, 5.1 and 6, PRD FR-1/FR-3 and the threat matrix now
   distinguish the current atomic rename from crash durability. Temporary-file flush/`fsync`, rename,
   and parent-directory `fsync` are hard prerequisites to receipt exposure or any shadow attempt.
   B2-W1 explicitly owns the durable-save/receipt-cursor implementation and crash tests. This is a
   future requirement, not a claim that the current writer already provides it.

2. **Receipt/replay ordering — CLOSED.** Receipt revision and identity are allocated and persisted with
   the locked legacy JSON mutation; FIFO enqueue occurs under that lock; one transaction per workflow
   prevents overtaking. Restart reads the durable legacy cursor/last identity rather than Postgres or
   process memory. The transaction decision tree distinguishes advance, exact replay, gap, stale,
   collision, and terminal conflict, and treats lost intermediate receipts as visible evidence rather
   than synthesized history.

3. **Projector/outbox ownership — CLOSED.** Immutable event rows are separated from mutable
   delivery-control rows. A narrowly permissioned delivery worker alone mutates lease/attempt/
   disposition metadata and cannot alter snapshots, event bytes, or live state. The lifecycle
   projector is pure/read-only and produces an in-memory view plus immutable evidence digest. The
   topology does not create a second lifecycle writer.

4. **Phase privacy — CLOSED.** Raw and model-derived phase text, identifiers, descriptions, and their
   hashes are prohibited. Only fixed coordinator/blueprint IDs present in a reviewed allowlist map to
   domain-separated opaque tokens; unknown values reject and park before persistence. Canary vectors
   cover syntactically valid phase inputs and every operational surface.

## Acceptance-criteria results

| # | Result | Assessment |
|---|---|---|
| 1 | PASS | The revised hypothesis is unambiguous and consistent across all three documents. |
| 2 | PASS | Only coordinator start, manual transition, and terminal commits participate; bypass and excluded mutations remain explicit. |
| 3 | PASS | Crash durability is a future hard prerequisite, and shadow reads cannot affect live execution, recovery, API results, or cutover. |
| 4 | PASS | Persistent lock-bound receipt order, ordered FIFO delivery, atomic CAS/outbox, restart behavior, replay branches, and terminal uniqueness are specified. |
| 5 | PASS | Empty-object allowlisting, opaque phase tokens, canary coverage, and low-cardinality telemetry close the privacy boundary. |
| 6 | PASS | Failure parks/disables only shadow work; rollback retains evidence and continues legacy authority. |
| 7 | PASS | Migration, runtime writer, delivery worker, read-only projector, and validator permissions are distinct; existing checkpoint objects are excluded. |
| 8 | PASS | Numeric latency, connection, queue, event, RSS, disk, retention, lag, parity, and trial limits remain owner-freezable. |
| 9 | PASS | The threat matrix covers durability, ordering/restart, replay, atomicity, privacy, delivery authority, resource bounds, bypasses, and false authority. |
| 10 | PASS | Instrumentation, integration-path Phase-0 checks, dashboard state, live failure tests, crash tests, and resource tests remain delivery gates. |
| 11 | PASS | Later slices have explicit ceilings; none is represented as an active lease or inherited authorization. |
| 12 | PASS | Q1/Q2, migration-owner selection, resource freeze, later implementation review, and trial activation remain explicit owner gates. |

## Mandatory challenge disposition

- The design does not assume the current rename is durable; every shadow attempt is gated after file
  and directory durability, with crash-reopen evidence required.
- Concurrent transitions cannot share a coordinator receipt revision under the specified lock/cursor
  contract; per-workflow single-flight delivery prevents overtaking, while lost intermediate receipts
  produce a parked gap.
- Exact replay is checked against the stored revision and event identity before a zero-row CAS becomes
  a mismatch; nonidentical collisions and post-terminal receipts park.
- Snapshot and immutable outbox event share one transaction. Delivery-control state is operational,
  separately permissioned, and cannot mutate lifecycle sources.
- Raw/model-derived phase data cannot enter bytes, hashes, logs, metrics, errors, or dashboard output;
  unknown mappings reject before database access.
- Existing checkpoint/backtrack/DLQ objects remain excluded, external legacy writers remain visible
  split-brain evidence, and no convergence claim is made.
- Retention remains separately reviewed and grants no runtime destructive privilege.
- Dashboard and `aq-qa` consume aggregate health and must state `legacy JSON authoritative`.
- The design retains bounded live-path latency requirements without allowing database availability to
  alter live status, body, execution, recovery, or authority.

## Authority conclusion

This `PASS` establishes only that the exact revised hypothesis is sufficiently specified for owner
adjudication. Q1 and Q2 remain undecided. The review does not authorize schema creation, DDL,
connections, code, runtime hooks, JSON mutations, shadow writes, deployment, traffic, writer
retirement, convergence-state changes, or a lifecycle cutover. Only after explicit Q1/Q2 decisions,
a named migration owner, and a frozen resource envelope may a separate B2-C1 authorization be
prepared and independently reviewed.

VERDICT: PASS — all twelve revised design criteria are satisfied; Q1/Q2 and every implementation or write remain separately gated
