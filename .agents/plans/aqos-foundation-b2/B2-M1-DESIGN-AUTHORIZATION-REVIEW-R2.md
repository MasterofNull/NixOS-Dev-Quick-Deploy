# Foundation B2-M1 design and authorization review — revision 2

**Review date:** 2026-07-18
**Reviewer:** Codex sub-agent `/root/b2_m1_review`
**Roles:** independent database migration architect, security/least-privilege reviewer, Nix integration reviewer, SRE, and contract reviewer
**Review type:** fresh exact-subject PREPARED_ONLY review; historical revision-1 findings remain preserved
**Overall verdict:** **REQUEST_REVISION**

## Exact revision-2 subject

| Subject | SHA-256 | Verdict |
|---|---|---|
| `.agents/plans/aqos-foundation-b2/B2-M1-DESIGN-PACKET.md` | `d3ce29ecba2ec7e03e14d1abbe3b4ed8f6272d89b001aac30ad37a37a055bd9c` | **REQUEST_REVISION** |
| `.agents/plans/aqos-foundation-b2/B2-M1-IMPLEMENTATION-AUTHORIZATION.md` | `e7c9774e291c145bda5330e9a3bbccbb79bc44dac7bc6b2a92ec2cb05878962a` | **REQUEST_REVISION** |

Any candidate change invalidates this verdict. The historical revision-1 review remains at
`678f99688556ade3942a056a0bdebb284a2c3a7d13165b86b7eb30c0ab9ac80a`; it was not overwritten or
relabelled.

## Evidence and focused validations

- Re-read the exact revision-2 subjects, B2 ADR/PRD/D0/C1 chain, canonical Alembic configuration and
  revisions, canonical migration test runner, deployed Nix migration caller, legacy migration tree,
  and the installed Alembic revision-resolution source.
- Recomputed the revision-2 subject hashes, all seven modified/new predecessor states, all read-only
  migration authority hashes, the C1 artifact hashes, and both bound Git identities. Every bound
  predecessor matches and all three proposed new paths remain absent.
- `nix eval --raw .#nixosConfigurations.hyperd-ai-dev.pkgs.python3Packages.alembic.version` previously
  established the deployed package as Alembic `1.18.1`; read-only Nix-store source inspection confirms
  `branch@head`, `branch@base`, and `branch@-n` parsing/filtering. No Alembic command or render was run.
- Repository static search confirms the only current unqualified canonical callers are the two paths
  now included in the seven-file ceiling: the Nix pre-start and `ai-stack/migrations/test-migrations.sh`.
- No candidate edit, Alembic invocation, migration import, database client/access, DDL, Nix activation,
  service action, deployment, staging, or commit occurred.

## Revision-1 finding closure

### R1 — canonical callers and exact candidate ceiling: **PARTIAL / REVISION REQUIRED**

Revision 2 correctly adds `ai-stack/migrations/test-migrations.sh`, binds its predecessor
`7fda4a9a503f99ae53ea88bd6e6dc32e67dcdcd001acd5be0ae3b44d9b984d3e`, and freezes seven
implementation files within D0's maximum-eight candidate inventory. Both forward calls become
`upgrade aidb@head`, which Alembic 1.18.1 supports and which cannot select the B2 root.

The rollback replacement is not acceptable. The current test performs `downgrade -1`, one revision.
Revision 2 mandates `downgrade aidb@base`, which traverses the complete AIDB lineage and executes every
AIDB downgrade, including the baseline table drops. The script has no disposable-database identity,
authorization token, or live-database denylist. This converts a branch-ambiguity fix into a materially
more destructive command and violates least surprise and the bounded-change objective.

Required revision: retain one-step semantics while qualifying the lineage (Alembic 1.18.1 source
supports the `branch@-n` form, so `aidb@-1` is the expected candidate subject), or move any full-base
round trip behind a separately proven disposable-database harness. Bind the exact intended behavior
and add a static assertion that the canonical runner contains neither an ambiguous target nor a
full-lineage destructive rollback.

### R2 — database-enforced CAS and immutable-outbox boundary: **CLOSED**

Revision 2 removes all writer table DML and grants only `EXECUTE` on one owner-controlled
`SECURITY DEFINER` function with a fixed `pg_catalog, aq_b2_workflow_shadow_v1` search path. The
function contract freezes expected/next revision, terminal, exact-replay, snapshot, immutable-outbox,
and initial-delivery-control behavior in one transaction. `PUBLIC` execution is revoked. Delivery and
reader grants cannot mutate lifecycle state or immutable event bytes.

The immutability statement is now honest: it applies only to the frozen ownership/grant topology and
does not claim resistance to superuser or owner compromise. Catalog ownership/membership, function
security/search path, grants, and trigger state are mandatory M1E evidence, while runtime attempts to
acquire ownership or trigger/function control must fail. This closes the prior CAS-bypass and
accidental-owner overclaim.

### R3 — bootstrap executor, ownership, version row, and cleanup: **PARTIAL / REVISION REQUIRED**

Revision 2 now distinguishes the token-bound ephemeral executor from the durable NOLOGIN owner,
freezes the executor's `CREATEROLE` and negative attributes, makes the fixture administrator own and
protect `public.alembic_version`, requires temporary role membership only inside the revision,
requires rollback evidence for roles/membership/objects/grants/version state, and explicitly cleans
the external bootstrap identity after success and failure. Those changes close the identity,
version-row, and cleanup ambiguities.

The specified privilege sequence cannot create the schema as written. Before migration, the
bootstrap executor has permission to connect and temporary row privileges on `alembic_version`, but
no database `CREATE` privilege. The newly created durable owner likewise has no database `CREATE`
privilege. After `SET LOCAL ROLE aq_b2_shadow_owner_v1`, PostgreSQL therefore denies schema creation.
`CREATEROLE` does not confer `CREATE` on a database.

Required revision: freeze the minimum temporary database-`CREATE` mechanism and its revocation. For
example, the disposable fixture administrator may grant the token-bound executor database `CREATE`,
the executor may create the explicitly named schema `AUTHORIZATION aq_b2_shadow_owner_v1`, and M1E
must prove revocation before commit/cleanup; or specify another least-privilege sequence that is
actually executable. The design must state the grantor, grantee, grant option, exact point of schema
creation, revocation owner, transaction boundary, and success/failure cleanup evidence. No durable
runtime role may retain database `CREATE`.

## Full gate reassessment

| Gate | Result | Assessment |
|---|---|---|
| Canonical Alembic authority | **PASS** | One configuration/version location remains authoritative; legacy tree is read-only and excluded. |
| Multiple-head resolution | **PASS** | Installed Alembic 1.18.1 supports `aidb@head`; AIDB and B2 identities are distinct roots/labels. Exact candidate graph remains an acceptance check. |
| Nix accidental auto-apply | **PASS** | The sole deployed call is restricted to an exact `upgrade head` to `upgrade aidb@head` substitution; no B2 hook is allowed. |
| Canonical test caller | **REVISION** | Qualified upgrades are correct, but `aidb@base` expands rollback from one revision to the whole lineage. |
| Exact seven-file ceiling | **PASS** | Seven implementation paths are explicitly bound within D0's maximum eight; governance evidence is not miscounted. |
| Revision identities | **PASS** | Revision ID, filename, branch, schema, policy and role identities are closed and consistent. |
| Runtime least privilege / CAS | **PASS** | Writer has function execution only; direct table DML and ownership/control paths are denied. |
| Outbox immutability | **PASS** | Trigger plus non-owner topology and catalog drift checks enforce the stated, correctly bounded guarantee. |
| Bootstrap/role creation | **REVISION** | Executor and durable owner lack the database `CREATE` privilege required by the specified schema-creation sequence. |
| Alembic version ownership | **PASS** | Fixture administrator owns the precreated version table; executor receives only temporary row privileges. |
| Transaction/failure rollback | **PASS WITH M1E GATE** | Durable roles, membership, schema, objects, grants and branch version are required to roll back together; external fixture cleanup is correctly separate. |
| Post-commit cleanup | **PASS** | CREATEROLE/version privileges, session and token-bound login are explicitly revoked/terminated/dropped after both outcomes. |
| Destructive B2 down | **PASS** | B2 `downgrade()` refuses before SQL; retained B2 state cannot be deleted under M1A. |
| Static non-connectivity | **PASS** | Default validation is offline/mocked and must fail before driver/DSN access; registry cannot select integration mode. |
| M1E isolation | **PASS** | Disposable execution remains separately hash-bound, expiring, loopback-only, denylisted and post-acceptance. |
| Resource/time bounds | **PASS** | SQL timeouts, one connection/attempt/database, 60-second suite and 256 MiB ceilings remain frozen. |
| Privacy/secret evidence | **PASS** | DSNs, credentials and high-cardinality workflow/event/phase/error values are prohibited from argv, logs and evidence. |
| Authority truth | **PASS** | M1A remains static-only; legacy JSON remains authoritative and no operational/runtime claim is permitted. |
| Predecessors and activation | **PASS** | All hashes/absences match; implementation remains single-use, owner-activated and expiring. |

## Per-subject conclusion

- **Design packet revision 2 — REQUEST_REVISION.** R2 is fully closed and most of R1/R3 is repaired,
  but the canonical rollback is over-broad and the schema creation sequence lacks required database
  privilege.
- **Implementation authorization revision 2 — REQUEST_REVISION.** Its exact grant would require an
  unsafe full-lineage AIDB downgrade and an unimplementable owner-role schema creation. Owner
  activation must not occur on this hash.

`VERDICT: REQUEST_REVISION — preserve branch-qualified one-step AIDB rollback and freeze a revocable temporary database-CREATE path for schema creation; all other original and revision-1 gates pass or remain correctly deferred to exact-candidate/M1E evidence.`
