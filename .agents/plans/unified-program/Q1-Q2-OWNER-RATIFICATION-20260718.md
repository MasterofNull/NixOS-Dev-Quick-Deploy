# Q1/Q2 owner ratification — 2026-07-18

**Owner:** `hyperd`  
**Decision date:** 2026-07-18  
**Authority type:** architecture and design-hypothesis ratification  
**Effect:** unblocks preparation and independent review of B2-C1 only

## Owner decision

The owner ratified Q1 and Q2 in the active Codex session:

> I ratify Q1: the Codex–Fable synthesis at SHA `00c7dbc5…` is the AQ-OS parent architecture,
> with the Unified Program Plan at SHA `2cab0bdd…` as its non-authoritative execution projection.
>
> I ratify Q2: the Foundation B2 workflow-run-task legacy-live/Postgres-shadow hypothesis frozen in
> commit `c11bf7a1`, including ADR `1bf65352…`, PRD `1496651e…`, and design packet
> `d8a0f368…`. I name `hyperd` as migration owner and freeze the complete PRD §9 resource envelope
> as written. This authorizes only preparation and independent review of B2-C1; it does not authorize
> implementation, DDL, database connections or writes, runtime hooks, deployment, traffic, cutover,
> later slices, cleanup, or rollback.

The abbreviated digests in the owner's statement resolve to the exact pre-ratification subjects below,
which were verified in the worktree before any projection was edited.

## Exact historical subjects

| Subject | Historical SHA-256 / commit |
|---|---|
| Codex–Fable synthesis | `00c7dbc5cadb24c4e4a4e7c1c66ad7ccc32d48a749dfd3de2d739445cdcbc163` |
| Unified Program Plan | `2cab0bdd2f560052f315a14be1b64b4e173cee7b4239dcac3e582af815924ac2` |
| Foundation B2-D0 commit | `c11bf7a12c8582d8554f3d816cf83e5a9edab15b` |
| workflow-run-task ADR | `1bf65352993d5496ca5f3f6d8d1aea9078ac9f21427464cda6a6360523ee02bb` |
| workflow-run-task PRD | `1496651ee11f20a82e953098489d866937ceb21d8cbda68553d5c18ea1b709c4` |
| B2-D0 design packet | `d8a0f368ea45bae47180aa73ba654af846941da8e98a682155729f94cd839d81` |
| independent B2-D0 review (`PASS`) | `6b97c09bfa1a79a928999533f779a3a4dfa59733b379ae318a47696bc781ec7e` |

The independent review passed the exact ADR, PRD, and design-packet bytes above. Subsequent status
edits to the synthesis, program plan, decision sheet, or PRD are projections of this owner decision;
they do not rewrite the reviewed subject or imply that the reviewer assessed the new projection bytes.

## Adjudication

- **Q1: RATIFIED.** The exact historical synthesis is the AQ-OS parent architecture. The exact
  historical Unified Program Plan is its non-authoritative execution projection.
- **Q2: RATIFIED.** The first shadow vertical is `workflow-run-task`, with legacy JSON remaining the
  live authority and Postgres used only as the proposed shadow target under the accepted D0 design.
- **Migration owner:** `hyperd`.
- **Resource envelope:** every value in the historical PRD §9 is frozen exactly as written. A later
  implementation may tighten a ceiling but may not relax it without fresh review and owner authority.
- **B2-D0:** accepted as design evidence at commit `c11bf7a12c8582d8554f3d816cf83e5a9edab15b`.
- **Newly unblocked:** prepare a hash-bound B2-C1 authorization and submit it for independent review.
- **Still unauthorized:** B2-C1 implementation and all DDL, database connection/write, runtime hook,
  deployment, live traffic, cutover, B2-M1 and later slices, cleanup, destructive action, and rollback.

This decision is not a transitive implementation authorization. A reviewed B2-C1 authorization must
name its exact file inventory, acceptance criteria, exclusions, hashes, and expiry before the owner can
activate implementation.
