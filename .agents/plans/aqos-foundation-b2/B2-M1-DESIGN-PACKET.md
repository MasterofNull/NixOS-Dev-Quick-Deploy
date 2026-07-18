# Foundation B2-M1 isolated migration boundary design packet

**Slice:** B2-M1 — canonical migration artifacts and isolated privilege evidence

**State:** REVISION 4 PREPARED FOR INDEPENDENT DESIGN REVIEW / NO IMPLEMENTATION OR DATABASE ACTIVITY AUTHORIZED

**Prepared:** 2026-07-18

**Migration owner:** `hyperd` under the ratified Q2 record

## 1. Outcome and negative authority

B2-M1 prepares one disabled-by-default database boundary for the accepted
legacy-live/Postgres-shadow hypothesis. It does not create a database authority, connect to Postgres,
apply DDL, grant a live principal, deploy a Nix change, or enable a runtime path.

The slice is deliberately split at the side-effect boundary:

1. **B2-M1A — artifact authoring:** a hash-bound implementer may author the canonical Alembic branch,
   a closed privilege policy, offline/static tests, and a future isolated integration harness. Every
   validation in M1A is non-connected.
2. **B2-M1E — ephemeral execution evidence:** after M1A receives exact-candidate acceptance and is
   committed, a separate expiring owner authorization may execute the accepted migration only in a
   disposable test database. M1E has no repository edits and cannot target the configured `aidb`
   database, a running service database, or any persistent operator database.

M1A and this packet do not authorize M1E. No passing static test is represented as migration,
privilege, rollback, or Postgres health evidence.

## 2. Framework inventory and authority decision

Repository evidence establishes two migration trees:

- **Canonical/deployed:** `ai-stack/migrations/alembic.ini`, selected by
  `nix/modules/services/mcp-servers.nix` and invoked by the `ai-aidb` pre-start as
  `alembic upgrade head`.
- **Legacy/unwired:** `ai-stack/database/postgres/migrations/`, which is not selected by the current
  Nix service and has a separate historical revision lineage.

B2-M1 must not revive the legacy tree or add a third runner. The canonical Alembic tree remains the
sole migration authority. The current unqualified `upgrade head` is unsafe for a dormant experimental
branch because adding a second head would either fail the service pre-start or make later edits prone
to accidental application.

The M1A candidate therefore makes the existing authority explicit:

- label the current AIDB lineage `aidb` at revision `20260125_01`;
- add a separate root branch labelled `b2_workflow_shadow` inside the same canonical version
  location;
- change only the existing Nix pre-start target from unqualified `head` to `aidb@head`;
- never add a B2 invocation, service, timer, hook, credential, or runtime membership.

The B2 branch is later selectable only by an exact, reviewed M1E command. Branch separation is not a
second authority: both lineages remain governed by the one canonical Alembic configuration and
version table. The graph snapshot was consulted only as an advisory topology index; every conclusion
above was verified against the source files.

## 3. Exact M1A candidate ceiling

The D0 packet describes a maximum eight-file **later migration candidate inventory**. Governance
design/authorization/review records are evidence, not implementation candidate files. Revision 1
incorrectly treated two governance records as consuming implementation slots. Revision 2 freezes an
exact seven-file implementation candidate, within the original maximum eight, and does not reserve or
authorize an eighth path.

| # | Operation | Path | Purpose |
|---:|---|---|---|
| 1 | MODIFY | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | label the existing canonical AIDB lineage `aidb`; no DDL change |
| 2 | NEW | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | dormant root revision labelled `b2_workflow_shadow` |
| 3 | MODIFY | `nix/modules/services/mcp-servers.nix` | replace only `upgrade head` with `upgrade aidb@head` |
| 4 | NEW | `config/workflow-shadow-db-privileges.json` | closed role/object/grant SSOT and migration identity |
| 5 | NEW | `scripts/testing/test-workflow-shadow-migration.py` | offline oracle by default; separately gated future disposable-DB mode |
| 6 | MODIFY | `config/validation-check-registry.json` | register only the non-connected default mode |
| 7 | MODIFY | `ai-stack/migrations/test-migrations.sh` | qualify both upgrades and the rollback to the `aidb` lineage only |

An eighth implementation file, any edit to `ai-stack/migrations/alembic.ini` or `env.py`, or any edit
under the legacy migration tree is a hard stop.

## 4. Database namespace and object contract

### 4.1 Fixed identities

| Kind | Exact identity |
|---|---|
| Alembic revision | `20260718_01_b2_shadow` |
| Alembic branch | `b2_workflow_shadow` |
| PostgreSQL schema | `aq_b2_workflow_shadow_v1` |
| durable object-owner role | `aq_b2_shadow_owner_v1` |
| runtime writer group role | `aq_b2_shadow_writer_v1` |
| delivery worker group role | `aq_b2_shadow_delivery_v1` |
| projector/validator group role | `aq_b2_shadow_reader_v1` |
| ephemeral M1E bootstrap executor | `aq_b2_m1e_bootstrap_<authorization-token>` |
| privilege-policy schema | `aq.workflow-shadow-db-privileges.v1` |

The four durable roles are `NOLOGIN` group roles. Before the revision starts, the M1E fixture
administrator creates the durable owner with exact `NOLOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
NOREPLICATION, NOBYPASSRLS`, grants it temporary `CREATE` on only the disposable database, and creates exactly one token-bound
bootstrap executor with `LOGIN, CREATEROLE, NOSUPERUSER, NOCREATEDB, NOREPLICATION, NOBYPASSRLS`,
permission to connect only to the disposable database, and no pre-existing B2 role membership. The
executor is not a durable migration authority or object owner. Before Alembic starts, the fixture
administrator creates and owns `public.alembic_version`, revokes `PUBLIC`, and grants the executor
only the temporary row privileges needed for version tracking.

The revision validates the pre-existing owner identity/attributes and the exact temporary database
`CREATE` grant, then creates only the writer, delivery, and reader NOLOGIN roles transactionally. The
owner is pre-created solely because a role must already exist to receive database `CREATE` before
`SET LOCAL ROLE` can create the schema. No runtime role receives database `CREATE`.

The schema contains exactly three separately named tables:

- `workflow_snapshot` — mutable only by the writer through expected-revision CAS;
- `workflow_outbox_event` — immutable event envelope and canonical event JSON, unique by event ID and
  `(workflow_id, revision)`;
- `workflow_delivery_control` — mutable lease/attempt/disposition data owned only by delivery.

No object may use, rename, depend on, query, or grant access to `public.workflow_checkpoints`,
execution-pattern, backtrack, graph-run, Redis/DLQ, or any existing workflow object.

### 4.2 Closed privilege matrix

`PUBLIC` receives no schema or table privilege. No runtime group owns the schema or a table.

| Principal | Schema | snapshot | outbox event | delivery control | Explicitly forbidden |
|---|---|---|---|---|---|
| durable owner | owns schema; `NOLOGIN`; no retained members | owner | owner | owner | LOGIN, runtime membership, live JSON access |
| writer | `USAGE`; execute CAS function only | none | none | none | direct table DML, DDL, delivery update, trigger control |
| delivery | `USAGE` | none | `SELECT` | `SELECT, UPDATE` | snapshot/event mutation, insert/delete, DDL |
| reader | `USAGE` | `SELECT` | `SELECT` | `SELECT` | every write, DDL, role membership |

The integration oracle uses test-only login roles that inherit exactly one runtime group role. It must
prove `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, direct snapshot/outbox/delivery writes by the writer,
event `UPDATE/DELETE`, snapshot write by delivery/reader, delivery update by writer/reader, trigger
disablement, function replacement, and `ALTER ... OWNER` all fail.

## 5. DDL and data invariants

The revision must use explicit schema-qualified identifiers and bound types. At minimum:

- identifiers are at most 128 characters and match the C1 opaque-ID contract;
- digests/tokens match `sha256:` plus 64 lowercase hexadecimal characters;
- revisions are `1..100000`, with unique `(workflow_id, revision)`;
- snapshot terminal/status/action consistency is enforced;
- canonical event JSON is an object, identifies `aq.workflow-shadow-event.v1`, and is at most 2 KiB
  in UTF-8 text form;
- outbox event ID and revision agree with the envelope columns;
- delivery lease epoch is `0..1000000`, attempt count is `0..1000`, disposition and typed error are
  closed enums;
- foreign keys bind outbox to the snapshot workflow and delivery control to the immutable event;
- the writer has no direct table DML. It receives `EXECUTE` only on one owner-controlled
  `SECURITY DEFINER` function, `apply_workflow_transition_v1`, whose fixed scalar/JSON arguments are
  validated against the C1 identities and whose `SET search_path` is exactly
  `pg_catalog, aq_b2_workflow_shadow_v1`;
- the function locks the target snapshot row, accepts insert only for
  `(expected_revision=0, revision=1)`, accepts update only where the stored revision equals the
  supplied expected revision and `revision=expected_revision+1`, enforces terminal uniqueness,
  distinguishes exact replay by stored event identity/digest, and atomically performs the snapshot
  mutation, immutable outbox insert, and initial delivery-control insert. Every mismatch returns a
  closed typed disposition without mutation;
- `PUBLIC` function execution is revoked; only the writer has `EXECUTE`. The runtime roles have no
  function ownership, schema `CREATE`, snapshot/outbox ownership, or trigger-control privilege;
- an owner-controlled trigger rejects every outbox `UPDATE` and `DELETE` under the accepted ownership
  and grant topology;
- no free-form error, objective, prompt, note, output, tool data, path, environment, raw phase ID, or
  model-derived phase text column exists.

The immutability guarantee applies to the frozen topology: durable owner is `NOLOGIN`, has no retained
members, and all runtime roles are non-owners. It does not claim protection from a PostgreSQL
superuser, compromise of the durable owner, or an externally authorized ownership change. M1E must
compare catalog ownership, memberships, function security/search-path settings, grants, and trigger
enabled state to the policy before and after every adversarial test. Any drift parks/fails evidence;
runtime-role attempts to acquire ownership or disable/replace the trigger/function must be denied.

The migration must not insert workflow rows, seed synthetic events, backfill legacy JSON, copy source
documents, or define an automatic repair procedure.

## 6. Transaction, lock, timeout, and resource rules

### Forward migration

- one Alembic revision transaction with `transactional_ddl` preserved;
- fail before any statement when the selected branch, revision identity, privilege-policy digest, or
  expected PostgreSQL dialect is wrong;
- acquire a transaction-scoped advisory lock derived from the fixed revision identity;
- set `lock_timeout = 2s`, `statement_timeout = 10s`, and `idle_in_transaction_session_timeout = 15s`
  locally for the migration transaction;
- never use `CREATE ... IF NOT EXISTS` to accept an ambiguous predecessor; pre-existing B2 names are a
  collision and fail closed;
- while still the ephemeral executor, validate the fixture-created owner and temporary database
  `CREATE`, create the other three NOLOGIN roles, grant the durable
  owner role to the executor inside the transaction, then `SET LOCAL ROLE` to that
  owner for schema/table/CAS-function/immutability-function/trigger creation;
- before returning to Alembic, `RESET ROLE`, revoke durable-owner membership and admin option from the
  executor, apply only the closed runtime grants, and verify the executor has no B2 membership;
- leave exactly four durable NOLOGIN roles total (one fixture-created owner plus three
  revision-created runtime roles), one schema, three tables, required indexes,
  constraints, one CAS function, and the immutability trigger/function;
- leave the B2 runtime unconfigured and unconnected after commit.

Alembic's version row remains updated by the bootstrap connection after `RESET ROLE`; its table is
owned by the fixture administrator, not the bootstrap or a B2 role. Immediately after successful M1E
commit, the administrator revokes database `CREATE` from the durable owner, verifies catalog ACLs,
revokes the executor's Alembic-version privileges and `CREATEROLE`,
terminates the bootstrap session, and drops the token-bound bootstrap login. Post-migration state
therefore retains only the four NOLOGIN roles, exact object
ownership/grants, and no login membership. Future live bootstrap identity or privilege design is
explicitly out of scope and cannot be inferred from this disposable-test executor.

### Failure and rollback

Any failed statement rolls back the whole forward transaction. M1E must inject a failure after role
creation/temporary membership and between object/grant creation, then prove that the three
revision-created roles, membership, schema, table, function, trigger, grant, or B2 Alembic branch
version row do not survive. The pre-existing owner/bootstrap are fixture state: the failure finalizer
must revoke owner database `CREATE`, verify the ACL removal, revoke executor privileges, terminate/drop
the executor, and drop the owner after proving it owns no object. Success retains the owner only after
catalog proof that database `CREATE` and all membership have been revoked.

### Down migration

Destructive down migration is forbidden. `downgrade()` must raise a typed, stable refusal before
issuing SQL. Operational disablement is role membership/credential absence and, in later separately
authorized rollback work, revocation of runtime memberships—not table deletion or history mutation.
The disposable M1E database may be destroyed as test-fixture cleanup because it is proven non-live and
contains no retained evidence. No production or persistent database cleanup is authorized here.

### Frozen resource envelope

M1 cannot relax PRD section 9. Static policy must freeze the 2 KiB event and 100,000-revision/event
ceilings, no runtime destructive retention, and the future pool ceilings. M1E additionally caps one
disposable database, one bootstrap migration connection, three test-role sessions sequentially, a 60-second
whole-suite deadline, and 256 MiB maximum measured database size. Crossing a limit fails and parks the
evidence run; it never retries against another database.

## 7. Non-connectivity evidence for M1A

The registered focused test may parse Python/JSON/Nix as text or AST and may import the migration
module only with mocked Alembic operations. It must prove:

1. exactly one canonical migration configuration remains selected;
2. the AIDB service target is exactly `aidb@head`, never unqualified `head`;
3. `ai-stack/migrations/test-migrations.sh` uses `upgrade aidb@head` for both forward calls and
   Alembic-1.18.1-supported `downgrade aidb@-1` for its branch-qualified one-step rollback, preserving
   the current single-revision semantics and never selecting singular `head`, unqualified `-1`, or B2;
4. the B2 revision is a separate root labelled `b2_workflow_shadow`;
5. object names, constraints, roles, grants, timeouts, advisory lock, transaction and refusal-only
   downgrade match the closed policy;
6. no LOGIN, password, credential read, database creation, live database name, connection constructor,
   socket, subprocess, `psql`, deployment, service, runtime hook, or B2 invocation exists in M1A;
7. the test's future integration mode exits before reading a DSN or importing a database driver
   unless explicit `--integration`, `--dsn-file`, and a later M1E evidence token are all present;
8. the validation registry invokes only the static oracle.

Permitted M1A commands are file hashing, Python compilation, JSON parsing/schema validation, Nix
evaluation/static checks that do not deploy, the static focused test, `aq-qa 0 --machine`, and Tier-0.
Running Alembic online or offline, the integration harness, `psql`, a database client, a service
restart, or a deployment is prohibited during M1A.

## 8. M1E disposable execution preconditions

A later M1E authorization must bind all seven accepted M1A hashes, the exact integration command, a
fresh disposable database identifier, DSN-file path class, PostgreSQL server identity, evidence
directory, implementer/operator identity, start/expiry no longer than two hours, and cleanup proof.
The harness must refuse:

- database names `aidb`, `postgres`, `template0`, `template1`, or any name not beginning with the
  authorization's random `aq_b2_m1e_` prefix;
- a non-loopback host, configured service DSN, shared credential file, pre-existing schema, or database
  not created by the same evidence token;
- a server or database with any non-test B2 object or unexpected connection;
- execution after expiry or reuse of a consumed token.

M1E success requires forward atomicity, privilege positives/negatives, immutability, CAS/uniqueness,
refusal-only down migration, injected-failure rollback, resource ceilings, and cleanup verification.
It still does not authorize runtime credentials, deployment, service wiring, shadow writes from the
coordinator, traffic, or cutover.

## 9. Threat model and mandatory reviewer challenges

| Threat | Control / required evidence |
|---|---|
| accidental live apply on deploy | named Alembic branches; Nix remains pinned to `aidb@head`; static negative scan |
| second migration authority | legacy tree untouched; canonical config/version location is sole selectable authority |
| broad DB-owner runtime | token-bound bootstrap is disposable/test-only; durable owner and runtime roles are NOLOGIN with no retained membership |
| schema/object collision | no `IF NOT EXISTS`; fail before ambiguous adoption |
| partial DDL/grants | one transaction plus injected-failure rollback evidence in M1E |
| destructive rollback | refusal-only `downgrade`; disposable DB cleanup only under M1E token |
| CAS bypass/outbox tampering | writer executes only owner CAS function; runtime roles are non-owners; catalog/grant/trigger drift and negative ownership tests |
| principal privilege creep | closed policy SSOT and exact information-schema comparison |
| secret/DSN leakage | DSN-file only, redacted diagnostics, no value in argv/log/evidence |
| test targets live DB | denylisted names, loopback-only, random prefix, token-bound creation proof |
| resource/lock exhaustion | local SQL timeouts, advisory lock, whole-suite deadline, no retry/fallback |
| false completion claim | M1A reports static readiness only; M1E separately reports ephemeral evidence |
| false authority claim | every artifact states `legacy JSON authoritative`; no runtime path exists |

An independent architecture/security/SRE/database reviewer must challenge every row and specifically
verify Alembic branch behavior against the installed version before this design may support an
implementation authorization.

## 10. Stop conditions and explicit exclusions

Stop and prepare a new reviewed amendment if implementation would require:

- using the legacy/unwired migration tree, adding another migration framework, or changing canonical
  Alembic `env.py`/configuration;
- an unqualified migration target, multiple active migration authorities, a production-role grant,
  a LOGIN role, credential creation, or persistent database access;
- database/DDL execution, an offline Alembic invocation, the test's integration mode, a service action,
  deployment, or Nix activation during M1A;
- an existing object mutation, existing checkpoint reuse, destructive down migration, data backfill,
  event repair, history synthesis, or retention deletion;
- any runtime hook, pool, client, writer, worker, projector, dashboard, API, Phase-0 operational-health
  claim, traffic, cutover, cleanup of retained state, or writer-convergence claim;
- a changed predecessor, shared-file conflict, eighth implementation file, or need to relax a frozen
  budget.

## 11. Acceptance and next gates

This design is acceptable only after an independent exact-hash `PASS`. That `PASS` authorizes no
implementation. The orchestrator may then prepare a single-use M1A authorization bound to this packet
and exact predecessor hashes. Owner activation of that authorization must name one bounded implementer
and an expiry no longer than 24 hours.

After an exact seven-file M1A candidate receives independent acceptance and is committed, M1E still
requires its own design/authorization/review/owner activation. B2-W1, B2-P1, B2-O1, B2-T1, all runtime
database activity, deployment, traffic, cutover, cleanup, and authority changes remain unauthorized.

`RECORD: DESIGN_ONLY. No implementation, migration execution, database connection/read/write, DDL,
grant, service action, deployment, runtime adoption, traffic, cutover, or cleanup is authorized.`

## 12. Revision history

Revision 1 subjects `d5a10d59470bda64a14cef33aeafaae305d998809749cc8a97e4a7ae912e10d8`
and `ee70a8daf80369165d876e87a26c45e9252916856a0121c95c7c5320ec817f59` received
`REQUEST_REVISION` in the independent review at
`ed816d7d02c237216ffb85678dc16b03fc07429eef19d75afd8d20a809fc30f4`. Revision 2 retains that
finding as historical evidence and addresses its three blockers: all canonical callers are now in
inventory, CAS is database-enforced through a closed non-owner interface, and the disposable
bootstrap executor is separated from durable NOLOGIN ownership with explicit rollback/cleanup proof.

Revision 2 subjects `d3ce29ecba2ec7e03e14d1abbe3b4ed8f6272d89b001aac30ad37a37a055bd9c`
and `e7c9774e291c145bda5330e9a3bbccbb79bc44dac7bc6b2a92ec2cb05878962a` received
`REQUEST_REVISION` at `26e3fad6d524d2d88d39ec0eedb63a1f083109260b1160a45d6def827603a052`.
Revision 3 changes only its two remaining findings: branch-qualified one-step AIDB rollback and the
temporary, revocable database-`CREATE` bootstrap path. The passed CAS/outbox boundary is unchanged.

Revision 3 received independent `PASS` at normalized review SHA-256
`09e994c8f7fa7e9df11f0b00d412d7304d523187568e61bce8a3c95483d085f1`. Revision 4 changes no
architecture, authority, implementation inventory, or acceptance semantics; it only normalizes
authorization whitespace and rebinds historical normalized review hashes.
