# Foundation B2-M1 design and authorization review — revision 3

**Review date:** 2026-07-18
**Reviewer:** Codex sub-agent `/root/b2_m1_review`
**Roles:** independent database migration architect, security/least-privilege reviewer, Nix integration reviewer, SRE, and contract reviewer
**Review type:** final exact-subject PREPARED_ONLY review; no implementation or execution acceptance
**Overall verdict:** **PASS**

## Exact revision-3 subject

| Subject | SHA-256 | Verdict |
|---|---|---|
| `.agents/plans/aqos-foundation-b2/B2-M1-DESIGN-PACKET.md` | `20d1dcdd7739c982a9d211ed0c58bea98eab09e8d10fe35f0c00515dcefbabb0` | **PASS** |
| `.agents/plans/aqos-foundation-b2/B2-M1-IMPLEMENTATION-AUTHORIZATION.md` | `8220ed9a1e442d1c9adffe00052ebce69120345315b20780cc0460a1fde1e5ba` | **PASS** |

Any subject-byte change invalidates this verdict. The historical revision-1 and revision-2
`REQUEST_REVISION` records remain preserved and are not acceptance evidence for this subject.

## Evidence and validations

- Re-read the exact revision-3 subjects and the accepted B2 ADR/PRD/D0/C1 chain.
- Recomputed every bound predecessor and read-only SHA-256, both Git identities, and all three required
  new-file absences. Every value matches the authorization.
- Rechecked the canonical Alembic configuration/revisions, Nix pre-start caller, canonical migration
  test runner, legacy migration tree, and installed Alembic 1.18.1 revision-resolution source.
  Read-only source confirms branch-qualified `branch@head`, `branch@base`, and `branch@-n` support;
  specifically, `aidb@-1` preserves one-step semantics while restricting lineage selection.
- Static repository search confirms the two canonical callers affected by the future seven-file
  candidate are the Nix pre-start and `ai-stack/migrations/test-migrations.sh`.
- No Alembic command/render, migration import, database access, DDL, Nix activation, service action,
  deployment, candidate edit, staging, or commit occurred.

## Remaining-finding closure

### Branch-qualified one-step rollback — **CLOSED**

Both canonical test upgrades are frozen as `upgrade aidb@head`; the rollback is now exactly
`downgrade aidb@-1`. The authorization prohibits singular `head`, unqualified `-1`, full-lineage
rollback, generic multi-head targets, and any B2 target. The static oracle must assert the exact two
forward calls and one one-step rollback. This preserves the current rollback depth, avoids the
revision-2 `aidb@base` teardown, and prevents accidental B2 selection.

### Disposable database CREATE and cleanup — **CLOSED**

The M1E fixture administrator—not M1A or a runtime principal—precreates the exact durable owner as
`NOLOGIN` with all elevated attributes disabled, grants it temporary `CREATE` only on the token-bound
disposable database, and creates the separately constrained bootstrap executor. The migration must
validate the owner attributes and exact database ACL before any statement, create only the other
three durable roles, temporarily grant owner membership to the executor, and use `SET LOCAL ROLE` for
schema/object creation.

On success, the administrator revokes owner database `CREATE`, proves the database ACL and membership
catalogs match policy, revokes executor version-table/`CREATEROLE` privileges, terminates the session,
and drops the bootstrap login. On injected failure, the revision-created roles, membership, schema,
objects, grants, and B2 version row must roll back; the external finalizer then revokes/proves removal
of owner `CREATE`, removes executor privileges/session/login, and drops the owner only after proving it
owns no object. No runtime role or persistent/live database receives database `CREATE`.

### CAS and immutable-outbox boundary — **PRESERVED**

The writer retains no direct table DML. It receives only `EXECUTE` on the owner-controlled fixed-
search-path `SECURITY DEFINER` CAS function, which enforces revision/terminal/exact-replay decisions and
atomically mutates snapshot plus inserts immutable outbox and initial delivery control. Runtime roles
remain non-owners; `PUBLIC` execution is revoked; trigger/function/ownership drift is catalog-gated;
the guarantee remains accurately bounded against superuser/owner compromise.

## Full gate result

| Gate | Result |
|---|---|
| canonical Alembic authority and legacy-tree exclusion | **PASS** |
| installed Alembic branch/multiple-head resolution | **PASS** |
| Nix `aidb@head` preservation and no B2 auto-apply | **PASS** |
| canonical test `aidb@head` / one-step `aidb@-1` | **PASS** |
| exact seven-file ceiling within D0 maximum eight | **PASS** |
| revision/branch/schema/policy identity consistency | **PASS** |
| database-enforced CAS and atomic outbox/delivery tuple | **PASS** |
| immutable event and runtime non-owner threat boundary | **PASS** |
| disposable bootstrap/NOLOGIN owner/temporary CREATE | **PASS** |
| `alembic_version` ownership and temporary row privileges | **PASS** |
| transactional failure rollback and external finalizer | **PASS** |
| success revoke/catalog proof and bootstrap cleanup | **PASS** |
| refusal-only B2 downgrade and no retained-data cleanup | **PASS** |
| static M1A non-connectivity and dormant M1E separation | **PASS** |
| resource, timeout, privacy, and secret-redaction bounds | **PASS** |
| legacy-JSON authority truth and no operational claim | **PASS** |
| predecessor hashes, single-use activation, expiry, stops | **PASS** |

## Per-subject conclusion

- **Design packet revision 3 — PASS.** The migration topology, least-privilege bootstrap, CAS/outbox
  boundary, failure semantics, evidence boundary, and negative authority are sufficiently frozen for
  a bounded M1A candidate.
- **Implementation authorization revision 3 — PASS.** The exact seven-file, offline-only grant is
  internally consistent and ready for a separate explicit owner activation naming its exact hash and
  required implementer.

This `PASS` does not activate M1A or authorize Alembic, offline SQL rendering, a database connection,
DDL, M1E, service/deployment activity, runtime adoption, traffic, cutover, cleanup, rollback, or any
later B2 slice.

`VERDICT: PASS — revision 3 preserves every accepted architecture/security/SRE gate, restores branch-qualified one-step AIDB rollback, and freezes a disposable-only temporary CREATE path with exact success/failure revocation evidence; implementation remains PREPARED_ONLY pending owner activation.`
