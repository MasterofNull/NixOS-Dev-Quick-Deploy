# Foundation B2-M1A migration-artifact implementation authorization — revision 4

**Authorization ID:** `auth-aqos-foundation-b2-m1a-20260718`
**Idempotency key:** `aqos-foundation-b2:b2-m1a:canonical-migration-artifacts:v1:20260718`
**Status:** **PREPARED_ONLY — IMPLEMENTATION AND DATABASE ACTIVITY NOT AUTHORIZED**
**Base commit:** `19c78faaf5ab6d3635ac05a80fd5ba3c63cb1aae`
**Required implementer identity on activation:** `codex-subagent-b2-m1a-implementer`
**Activation rule:** an independent reviewer must first issue `PASS` on this exact document hash.
Implementation then requires a later owner statement naming this exact hash, the required implementer,
an activation timestamp, and an expiry no longer than 24 hours. Broad preauthorization, design review,
silence, or this record's existence does not activate it.
**Single use:** consumed by the first complete exact seven-file candidate report. An interrupted attempt
without a complete report may resume only with the same implementer after all predecessors are
reverified.

## 1. Bound predecessor chain

Every subject below is a read-only input. A mismatch is a hard stop and requires a fresh authorization
subject and independent review.

| Subject | SHA-256 / Git identity |
|---|---|
| accepted B2-C1 implementation commit | Git `8e285cdd978f2fc020393ac4327747f3e8f31476` |
| current candidate base | Git `19c78faaf5ab6d3635ac05a80fd5ba3c63cb1aae` |
| `WORKFLOW-SHADOW-ADR.md` | `1bf65352993d5496ca5f3f6d8d1aea9078ac9f21427464cda6a6360523ee02bb` |
| `WORKFLOW-SHADOW-PRD.md` | `b40b96420e03d84e75b848b5535cd6b16e46818e3a74d7dbb526369e8b71d7d5` |
| `B2-D0-DESIGN-PACKET.md` | `d8a0f368ea45bae47180aa73ba654af846941da8e98a682155729f94cd839d81` |
| `B2-D0-DESIGN-REVIEW.md` | `6b97c09bfa1a79a928999533f779a3a4dfa59733b379ae318a47696bc781ec7e` |
| `B2-C1-IMPLEMENTATION-AUTHORIZATION.md` | `db657588b7d256ad2c518958b2875cc1fa46eea6955421043930d9c62bdc5093` |
| `B2-C1-AUTHORIZATION-REVIEW.md` | `49e6d3b1ae7bd18d2a708401062e62c3258dcca1683d31ccc5a648b133b26b56` |
| `B2-C1-IMPLEMENTATION-ACCEPTANCE.md` | `12a06a4a126eb886d2216033f41c3d0eccbe8ce195200ec9122b899d72240951` |
| `B2-M1-DESIGN-PACKET.md` revision 4 | `020462d0ec3222bc893c7543712856a80ce8acb92b5b9caa48ab3a902e1860aa` |
| revision-1 design/authorization review (`REQUEST_REVISION`) | `ed816d7d02c237216ffb85678dc16b03fc07429eef19d75afd8d20a809fc30f4` |
| revision-2 design/authorization review (`REQUEST_REVISION`) | `26e3fad6d524d2d88d39ec0eedb63a1f083109260b1160a45d6def827603a052` |
| revision-3 design/authorization review (`PASS`) | `09e994c8f7fa7e9df11f0b00d412d7304d523187568e61bce8a3c95483d085f1` |
| C1 closed-contract schema | `16152812b25c02455ebbef15fa83ff606634ca58155206c4610ed2292ddbbf35` |
| C1 phase-token registry | `5d63f844737037db9ea6d2e4a0b3e6488245e655a0058063db75feccaeb807ef` |
| C1 pure oracle | `2523c66c8cc675c6470ec3e9c536ab0efdf78e0587c4c1b09ef9bea27e922266` |
| C1 golden vectors | `c793ed7761fe31b6551c6bc3faf6926bbb95a7c3c2b080c2876779fc1a8f5d4b` |

Legacy `workflow-sessions.json` remains authoritative. This grant cannot connect to or modify a
database and cannot make the B2 shadow operational.

## 2. Exact seven-file ceiling and predecessors

One bounded implementer owns all seven paths. New paths must remain absent and modified paths must
match their predecessor before the first edit.

| # | Operation | Path | Frozen predecessor |
|---:|---|---|---|
| 1 | MODIFY | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `a65ca831b4217aa0057397ed18341ce218e6e55e3aef130f6a15fb87a323f640` |
| 2 | NEW | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | must be absent |
| 3 | MODIFY | `nix/modules/services/mcp-servers.nix` | `473e4613159786d5ee485a87d14e26b7be11947063c2e4fee2941f91db8e7b50` |
| 4 | NEW | `config/workflow-shadow-db-privileges.json` | must be absent |
| 5 | NEW | `scripts/testing/test-workflow-shadow-migration.py` | must be absent |
| 6 | MODIFY | `config/validation-check-registry.json` | `13e14031008becdc15c814428853244b94490853ed05e270dee8862e15900d02` |
| 7 | MODIFY | `ai-stack/migrations/test-migrations.sh` | `7fda4a9a503f99ae53ea88bd6e6dc32e67dcdcd001acd5be0ae3b44d9b984d3e` |

Read-only migration authority inputs:

| Path | SHA-256 |
|---|---|
| `ai-stack/migrations/alembic.ini` | `981243256c6cd411f8a26aa97cc9776e63fae27e06997274bcded078b6c52a2c` |
| `ai-stack/migrations/env.py` | `f7dea19ec9711f2b20e5dbfb895f5b38e44b5b9276d47960c1b0dcbfd65ab6ec` |
| `ai-stack/migrations/versions/20260109_01_baseline_schema.py` | `9866dd1685bfa233c9294450eb90fb49a97b28bf44696c6cae6b695d57506c3e` |
| `ai-stack/migrations/versions/20260109_02_pgvector_hnsw_index.py` | `b998e87a2da44212e31a5748da397c8486a6b7401088d787efcbf49415329651` |
| legacy/unwired `ai-stack/database/postgres/migrations/env.py` | `d3d540786d97ba819e10e922e9088ea2fceeab6c67535b2bf76d6ccb9844a95e` |

The D0 ceiling applies to the later migration candidate, not governance evidence. These exact seven
implementation files remain within its maximum eight; no eighth path is authorized. The legacy tree
and every read-only input must remain byte-identical. An eighth implementation file is a hard stop.

## 3. Exact M1A grant

### 3.1 Canonical Alembic lineage isolation

File 1 may change only `branch_labels` from `None` to the single label `aidb`. Its revision,
`down_revision`, upgrade body, downgrade body, imports, and every other byte-level behavior must remain
semantically unchanged.

File 2 must be a new root revision with:

- revision `20260718_01_b2_shadow`;
- `down_revision = None`;
- exactly one branch label, `b2_workflow_shadow`;
- no dependency on the AIDB lineage or any legacy migration lineage;
- schema-qualified DDL for only the identities in the design packet;
- no connection creation, settings/secret read, subprocess, `psql`, service, runtime import, or
  automatic execution.

File 3 may change only the existing `ai-aidb` pre-start Alembic target from `upgrade head` to
`upgrade aidb@head`. It must not add a B2 command, role, user, secret, service, dependency, timer,
activation, or deployment hook. This edit preserves the existing live migration lineage and makes the
dormant branch non-selectable by the service.

File 7 must replace both canonical-test `upgrade head` calls with `upgrade aidb@head` and replace
`downgrade -1` with Alembic-1.18.1-supported `downgrade aidb@-1`. No other shell behavior may change.
The rollback remains exactly one revision and branch-qualified to AIDB; no command may select, apply,
downgrade, or stamp B2. Bash/static checks must prove there is no singular `head`, unqualified `-1`,
or full-lineage rollback.

### 3.2 Closed privilege and object policy

File 4 must be closed JSON with schema identity `aq.workflow-shadow-db-privileges.v1`. It is the exact
SSOT consumed by both tests and must include:

- migration and branch identities;
- schema/table/function/trigger names;
- the durable NOLOGIN owner, writer, delivery, and reader group roles plus the token-bound M1E
  bootstrap-executor pattern;
- the complete positive and negative privilege matrix from the design packet;
- exact schema/object/column/constraint/index/foreign-key/trigger expectations;
- local lock/statement/idle-transaction timeout values;
- limits: 2 KiB event, revision 100,000, lease epoch 1,000,000, attempt count 1,000, disposable suite
  60 seconds, and database 256 MiB;
- denylisted database names and required `aq_b2_m1e_` prefix;
- authority string `legacy_json_authoritative` and coverage state `static_only`.

Every object boundary is closed; unknown fields, duplicate identities, broad wildcard privileges,
durable LOGIN roles, `PUBLIC` grants, or unqualified objects reject. The policy must distinguish the
ephemeral bootstrap executor from the durable owner and freeze its exact temporary attributes,
membership transitions, cleanup, and threat boundary.

### 3.3 Forward-only dormant migration semantics

File 2 may declare future SQL operations, but M1A may not execute or render them through Alembic. The
revision must require one transactional forward application and fixed local controls:

- transaction-scoped advisory lock derived from the revision identity;
- `lock_timeout = 2s`;
- `statement_timeout = 10s`;
- `idle_in_transaction_session_timeout = 15s`.

It must fail on any pre-existing B2 role/schema/object rather than use `IF NOT EXISTS` to adopt unknown
state, except for the exact fixture-created durable owner. It creates only the other three NOLOGIN
roles, one schema, three tables, required
constraints/indexes, one `SECURITY DEFINER` CAS function, and the immutable-event trigger/function. It
grants only the closed matrix. `PUBLIC` is revoked.

Before the revision, M1E—not M1A—must have the fixture administrator create the durable owner with
exact `NOLOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS`, grant that owner
temporary `CREATE` only on the disposable database, and create one token-bound bootstrap executor with
`LOGIN, CREATEROLE, NOSUPERUSER, NOCREATEDB, NOREPLICATION, NOBYPASSRLS`, connectivity limited to
the disposable database, and no B2 membership. Within the single revision transaction, that executor
uses a fixture-administrator-owned, precreated `public.alembic_version` table with only temporary row
privileges and no `PUBLIC` access. It validates the owner attributes and exact database ACL, creates
only the writer/delivery/reader NOLOGIN roles, temporarily grants itself the durable owner role,
uses `SET LOCAL ROLE aq_b2_shadow_owner_v1` to create every B2 schema/table/function/trigger, then
`RESET ROLE` and revokes its owner membership/admin option before Alembic records the branch version.
After commit, the fixture administrator revokes database `CREATE` from the owner, proves the database
ACL and role memberships match policy, revokes executor Alembic-version privileges and `CREATEROLE`,
terminates the session, and drops the bootstrap login. The only retained identities are the four NOLOGIN roles, with the durable
owner owning every B2 object and no retained role members.

The writer receives schema `USAGE` and `EXECUTE` only on
`apply_workflow_transition_v1`; it receives no direct table DML. The owner-controlled function has
fixed typed arguments, an exact `SET search_path` of `pg_catalog, aq_b2_workflow_shadow_v1`, explicit
expected-revision/next-revision and terminal predicates, exact-replay identity/digest handling, and
atomically mutates snapshot plus inserts immutable outbox and initial delivery control. `PUBLIC`
execution is revoked. Delivery receives only outbox `SELECT` and delivery-control `SELECT, UPDATE`;
reader receives `SELECT`; runtime roles cannot own/alter/drop/truncate tables, change ownership,
replace/disable functions/triggers, or obtain the owner role.

Outbox immutability is guaranteed only under this frozen ownership/grant topology. The candidate must
not claim resistance to a PostgreSQL superuser, compromise of the durable owner, or an externally
authorized ownership change. M1E must verify catalog ownership/membership, function security and
search path, grants, and trigger enabled state before/after adversarial tests; runtime ownership or
trigger/function-control attempts must fail and any detected drift fails/parks evidence.

The revision must contain no workflow data/backfill, source JSON access, seed event, repair, retention
deletion, database creation, extension creation, LOGIN membership, password, credential, raw/model
phase field, free-form error field, or existing checkpoint reference.

`downgrade()` must issue no SQL and raise one stable typed refusal that states destructive downgrade is
prohibited. Failed forward application relies on transactional DDL rollback. Runtime disablement is
not implemented by M1A; roles remain NOLOGIN and no service receives membership or credentials.

M1E failure injection after role/membership creation and between object/grant creation must prove the
three revision-created roles, temporary memberships, schema, ownership, tables, functions, trigger,
grants, and B2 Alembic version row roll back together. The fixture-created owner/bootstrap do not roll
back with the revision. On failure the finalizer revokes owner database `CREATE`, proves ACL removal,
revokes executor privileges, terminates/drops the executor, and drops the owner only after proving it
owns no object. On success it retains the owner only after exact catalog proof of no database `CREATE`
and no membership.

### 3.4 Static oracle and future integration harness

File 5 must default to a standard-library-only, deterministic, offline, and bounded mode. It parses source/JSON/Nix
and may import File 2 only with fully mocked Alembic modules/operations. It must verify the complete
design contract, exact branch isolation, object/permission policy, SQL qualification, no ambiguous
`IF NOT EXISTS`, refusal-only downgrade, and all negative-authority constraints. It must prove no test
attempts a DNS lookup, socket, subprocess, database driver import, environment DSN read, or file write.

The same file may expose a dormant integration mode for later M1E. It must fail closed before importing
any database driver or reading a DSN unless all are present:

1. explicit `--integration`;
2. `--dsn-file`, naming a mode-`0600` regular non-symlink file; and
3. a separately specified M1E evidence token whose format and expiry are validated without logging
   either value.

Without those gates, direct invocation must return a stable `M1E_NOT_AUTHORIZED` skip/refusal and zero
network/process/database activity. The harness source must encode the later tests for atomic forward
application, all positive/negative privilege cells, outbox immutability, uniqueness/CAS constraints,
refusal-only downgrade, injected-failure rollback, size/time ceilings, and disposable cleanup. M1A
must not execute it.

File 6 may register one bounded check invoking only File 5's default offline mode with a timeout no
greater than 30 seconds. Its trigger paths are exactly the seven M1A implementation paths. It must not
pass `--integration` or `--dsn-file`, invoke Alembic/Postgres/Nix deployment, or use a shell runner.

The default oracle must also parse File 7 and require its exact two `upgrade aidb@head` calls and one
`downgrade aidb@-1` call, with no singular `head`, unqualified `-1`, B2 branch, full-lineage rollback,
or generic multi-head target.

## 4. Frozen authority, resource, and truth constraints

- Legacy JSON remains the sole live authority.
- M1A health/coverage output is exactly `authority=legacy_json_authoritative` and
  `coverage=migration_artifacts_static_only`.
- The C1 schemas, mapper, tokens, fixtures, and Phase-0 registrations remain read-only.
- M1A cannot claim DDL applied, schema ready, grants proven, rollback proven, database healthy,
  Postgres observing, service coverage, dashboard parity, or operational readiness.
- The complete PRD section 9 envelope remains frozen. The candidate may tighten but not relax it.
- The M1A test timeout is at most 30 seconds and uses no retry. The future M1E whole-suite timeout is
  at most 60 seconds and uses one disposable database and one migration attempt.
- No metric, log, error, test output, or evidence record may contain a DSN, credential, workflow ID,
  event ID, phase token, raw phase material, or free-form database error.

## 5. Mandatory stop conditions

Stop without workaround, partial implementation, or extra edits if any of the following is required
or observed:

- a database connection/read/write, DDL execution or rendering, Alembic command, integration-mode
  execution, `psql`, driver, socket, subprocess, service action, deployment, or Nix activation;
- editing canonical `alembic.ini`/`env.py`, using the legacy migration tree, adding a migration
  framework/runner, or leaving any unqualified `upgrade head`/`downgrade -1` in a canonical caller;
- a production/persistent database identity, durable LOGIN role, password/secret, retained bootstrap
  membership/attribute, live B2 grant, broad runtime owner use, public grant, unqualified object, or
  configured database name;
- `IF NOT EXISTS` adoption, destructive down migration, object/data deletion, existing object mutation,
  checkpoint reuse, backfill, seed event, repair, gap synthesis, or retention enforcement;
- runtime adapter/hook/pool/writer/worker/projector, API, dashboard, operational Phase-0 claim, service,
  traffic, cutover, writer retirement, convergence-state change, activation, cleanup, or rollback of
  retained data;
- drift in a predecessor/read-only hash, new-file presence, shared-file conflict, an eighth
  implementation file, changed implementation ownership, or a need to relax a budget.

Any stop requires a narrow amendment, new exact subject hash, independent review, and fresh owner
activation. The implementer may not infer authority from Q1/Q2 or the owner's broader program
direction.

## 6. Implementer, review, and integration rules

- Exactly one bounded implementer, `codex-subagent-b2-m1a-implementer`, owns all seven files after
  owner activation. It may not delegate, split ownership, stage, commit, deploy, activate, connect to
  a database, run Alembic, pass File 5's integration flags, or accept its own work.
- Before editing, the implementer records identity and verifies the base commit, every predecessor,
  every required absence, all read-only hashes, and lack of overlap with another agent.
- After each edit, the implementer reports exact file hashes, objective/root cause, key framework and
  security reasoning, validations, stopped/skipped commands, and explicit exclusions.
- A different agent/session must independently review the exact seven-file candidate as database
  migration architect, security/least-privilege reviewer, Nix integration reviewer, and SRE. The
  reviewer must not edit candidate bytes.
- The reviewer must challenge Alembic branch resolution against the installed version, Nix target
  preservation, all SQL/role/object constraints, down-migration refusal, integration-mode fail-
  closure, static non-connectivity, secret redaction, and every stop condition.
- Any reviewer edit makes that reviewer a material rewriter and recuses it from accepting the new
  hash. Any candidate byte change requires fresh independent review.
- Only the orchestrator may stage and commit after exact-hash `PASS`, all offline focused checks,
  compilation/JSON parsing, `aq-qa 0 --machine`, and Tier-0 pass.

No M1A review or commit authorizes M1E. M1E needs an exact post-commit execution packet, independent
review, and expiring owner activation before any database client is invoked.

## 7. Required M1A acceptance evidence

An independent reviewer may issue `PASS` only when all are true:

1. The subject is exactly the seven-file implementation ceiling and every predecessor/absence/read-only check passes.
2. The canonical tree remains the sole migration authority; the legacy tree is untouched.
3. The AIDB lineage is labelled `aidb`, the B2 lineage is a separate root labelled
   `b2_workflow_shadow`, and Nix selects only `aidb@head`.
4. The B2 migration identities, three tables, four durable NOLOGIN roles, token-bound disposable
   bootstrap executor, schema qualification, constraints, closed grants, public revocation, advisory
   lock, local timeouts, CAS function, and immutable-event trigger exactly match the closed policy.
5. Writer direct table DML is denied; only the fixed-search-path owner CAS function can advance the
   snapshot/outbox/delivery tuple. Runtime roles cannot acquire ownership or control the trigger/function,
   and the guarantee accurately excludes superuser/owner compromise.
6. Existing objects, durable login credentials, database creation, checkpoint reuse, backfill, repair,
   destructive B2 down, retained bootstrap membership, runtime membership, and operational activation are absent.
7. B2 `downgrade()` refuses before SQL; source-level forward failure covers roles, membership, objects,
   grants, ownership and branch version in one transaction, with external bootstrap cleanup explicit.
8. The static oracle covers every positive/negative policy cell and has zero database/network/process/
   file-write behavior.
9. The future integration mode refuses before driver/DSN access without all M1E gates and is not
   executed in candidate validation.
10. Both canonical test upgrades select `aidb@head`; its one-step rollback selects `aidb@-1`; no caller can
    select B2 or an ambiguous head.
11. The validation registry invokes only the default static oracle with a maximum 30-second timeout;
   no environment variable or env-contract entry is introduced.
12. Python compilation, Bash syntax, JSON parsing/closure checks, the static focused test,
    `aq-qa 0 --machine`, and
    Tier-0 pass with no Alembic command, database, socket, service, or deployment.
13. Evidence reports static artifact readiness only and states that legacy JSON remains authoritative.
14. No candidate or evidence claims migration execution, privilege proof, runtime adoption, dashboard
    parity, writer convergence, traffic, cutover, cleanup, rollback, or M1E authority.

## 8. Activation and consumption record

Current activation state: **NOT ACTIVATED**.

After a final independent authorization review passes this exact document, owner activation must
explicitly name:

- this authorization's exact SHA-256;
- implementer `codex-subagent-b2-m1a-implementer`;
- activation timestamp and expiry no more than 24 hours later; and
- confirmation that the seven-file implementation ceiling within D0's maximum eight-file candidate,
  non-connectivity rule, and all stop conditions are
  unchanged.

Until that record exists, none of the seven implementation files may be created or modified under this grant.

`RECORD: PREPARED_ONLY. M1A implementation, Alembic execution, offline SQL rendering, integration
harness execution, database connection/read/write, DDL, grants, service actions, deployment, runtime
adoption, traffic, cutover, M1E, later B2 slices, cleanup, and rollback remain unauthorized.`
