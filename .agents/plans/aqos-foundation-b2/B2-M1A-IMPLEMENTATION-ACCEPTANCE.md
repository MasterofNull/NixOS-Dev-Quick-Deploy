# Foundation B2-M1A implementation acceptance review

**Review date:** 2026-07-18 UTC
**Reviewer role:** independent database-migration architecture, security/least-privilege, Nix-integration, and SRE reviewer
**Authorization subject:** `B2-M1-IMPLEMENTATION-AUTHORIZATION.md`
**Authorization SHA-256:** `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906`
**Activated implementer:** `codex-subagent-b2-m1a-implementer`
**Activation window:** 2026-07-18T17:23:48Z through 2026-07-19T17:23:48Z
**Verdict:** **REQUEST_REVISION — PROCEDURAL_STOP; CANDIDATE NOT ACCEPTED**

## 1. Exact reviewed subject

The review independently recomputed the following exact seven candidate hashes:

| # | Path | SHA-256 |
|---:|---|---|
| 1 | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

The four modified paths contain only the authorized bounded changes: the existing AIDB head receives
the `aidb` label, the existing Nix pre-start target becomes `aidb@head`, the canonical migration test
uses two `upgrade aidb@head` calls and one `downgrade aidb@-1`, and the registry adds one bounded
offline-only check. The three new paths are the dormant B2 root, closed privilege/object policy, and
offline/static oracle. No eighth candidate path was presented.

The bound ADR, PRD, D0 packet/review, C1 authorization/review/acceptance, M1 design packet, historical
reviews, canonical Alembic inputs, and legacy migration-tree input were inspected or hash checked.
The canonical Alembic tree remains the only selected migration authority; the legacy migration tree
is unchanged. Legacy `workflow-sessions.json` remains the sole live state authority.

## 2. Procedural stop and containment

The implementer disclosed that it invoked:

```text
python3 scripts/testing/test-workflow-shadow-migration.py --integration
```

The command returned the stable `M1E_NOT_AUTHORIZED` refusal with exit status 77 because neither a DSN
file nor an M1E evidence token was supplied. The fail-closed ordering means this invocation did not
read a DSN, import a database driver, open a socket, create a subprocess, connect to PostgreSQL,
render or execute DDL, invoke Alembic, or mutate candidate bytes. Recomputed hashes after disclosure
match the exact subject above, so the incident is contained.

Containment does not cure the authority violation. Authorization sections 3.4 and 5 expressly prohibit
passing the integration flag or executing integration mode during M1A and classify either act as a
mandatory stop. The single-use authorization is therefore consumed and procedurally invalid for
acceptance of this candidate. A fail-closed result proves an important control, but it cannot be used
to retrospectively authorize the prohibited command.

## 3. Permitted offline evidence

Only offline/static validation continued after the disclosure:

| Validation | Result |
|---|---|
| `python3 scripts/testing/test-workflow-shadow-migration.py` | **PASS** — `authority=legacy_json_authoritative coverage=migration_artifacts_static_only` |
| Python compilation of the two migration sources and static oracle | **PASS** |
| JSON parsing of the privilege policy and validation registry | **PASS** |
| `bash -n ai-stack/migrations/test-migrations.sh` | **PASS** |
| source/diff review for branch targets, imports, connection/process surfaces, secrets, and forbidden adoption/destructive forms | **PASS for the static subject** |
| `aq-qa 0 --machine` | **PASS** (exit 0) |
| `scripts/governance/tier0-validation-gate.sh --pre-commit` | **PASS** (exit 0; focused checks and Phase-0 completed) |

Static review found the intended dormant topology: an isolated `b2_workflow_shadow` root, a closed
four-role NOLOGIN policy, token-patterned disposable bootstrap boundary, schema-qualified objects,
database-enforced expected-revision CAS plus atomic snapshot/outbox/delivery creation, fixed
`SECURITY DEFINER` search paths, `PUBLIC` revocation, immutable-outbox trigger, transaction-local
timeouts/advisory lock, and a refusal-only B2 downgrade. The Nix service and canonical migration test
select only the `aidb` branch. The registry invokes only default offline mode with a 30-second bound.

These are static observations, not database evidence. This review does not claim that PostgreSQL has
accepted the SQL, that Alembic has resolved or applied either branch, that the grant/rollback model has
been exercised, or that any schema is ready.

## 4. Required recovery gate

No candidate file may be accepted, staged, committed, executed, or treated as completing M1A under
the consumed authorization. Recovery requires all of the following:

1. preserve or deliberately revise the exact seven candidate bytes and recompute all seven hashes;
2. prepare a fresh narrow, single-use authorization bound to those exact hashes, this procedural-stop
   record, the unchanged no-connectivity boundary, and an explicit ban on integration-mode invocation;
3. obtain independent review of that new authorization subject;
4. obtain a fresh expiring owner activation naming the authorized acceptance/implementation role; and
5. repeat independent exact-hash acceptance using only the commands permitted by that fresh grant.

M1E remains unauthorized. No database client, driver, DSN, Alembic command, DDL render/execution,
PostgreSQL read/write, Nix evaluation/activation, service action, deployment, runtime hook, traffic,
cutover, dashboard claim, or retained-state cleanup was performed by this reviewer or authorized by
this record.

`VERDICT: REQUEST_REVISION — PROCEDURAL_STOP. The seven-file candidate is statically contained but is
not accepted because the implementer invoked explicitly forbidden M1A integration mode. The active
authorization is consumed; fresh hash-bound authorization, independent review, and owner activation
are required before acceptance can resume.`
