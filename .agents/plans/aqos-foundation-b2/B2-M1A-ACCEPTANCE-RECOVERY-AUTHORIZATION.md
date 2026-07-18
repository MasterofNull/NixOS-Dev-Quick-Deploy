# Foundation B2-M1A acceptance-recovery authorization

**Authorization ID:** `auth-aqos-foundation-b2-m1a-acceptance-recovery-20260718`
**Status:** **PREPARED_ONLY — NOT ACTIVATED**
**Prepared against Git commit:** `d847df06441aa1198000fbf57003c7c4285eb7d8`
**Required acceptance operator on activation:** `codex-subagent-b2-m1a-recovery-acceptance`
**Single use:** one exact-byte static acceptance verdict for the seven-file subject below
**Expiry rule:** owner activation must name this document's exact SHA-256, the required acceptance
operator, an activation timestamp, and an expiry no more than 24 hours later.

This is a procedural recovery grant, not an implementation amendment. It permits no candidate edit,
replacement, formatting change, generation, execution-capable integration check, or scope expansion.
It does not reactivate or cure the consumed implementation authorization.

## 1. Incident and predecessor bindings

All rows are immutable read-only evidence. Any mismatch consumes no authority and is a hard stop.

| Subject | Bound identity |
|---|---|
| procedural-stop and containment record, `B2-M1A-IMPLEMENTATION-ACCEPTANCE.md` | SHA-256 `2572e4ab858842ea272648d223c4cb503d8f8bfa1a123bb9680653211219532f` |
| original consumed authorization, `B2-M1-IMPLEMENTATION-AUTHORIZATION.md` | SHA-256 `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906` |
| accepted design, `B2-M1-DESIGN-PACKET.md` | SHA-256 `020462d0ec3222bc893c7543712856a80ce8acb92b5b9caa48ab3a902e1860aa` |
| revision-1 review (`REQUEST_REVISION`) | SHA-256 `ed816d7d02c237216ffb85678dc16b03fc07429eef19d75afd8d20a809fc30f4` |
| revision-2 review (`REQUEST_REVISION`) | SHA-256 `26e3fad6d524d2d88d39ec0eedb63a1f083109260b1160a45d6def827603a052` |
| revision-3 review (`PASS`) | SHA-256 `09e994c8f7fa7e9df11f0b00d412d7304d523187568e61bce8a3c95483d085f1` |
| revision-4 review (`PASS`) | SHA-256 `84cd8a5b2f8e5d272c548c40e0fe02e50d53333a2a13f57aa84f6e30ac16a6ce` |
| accepted B2-C1 implementation | Git `8e285cdd978f2fc020393ac4327747f3e8f31476` |

The procedural-stop record establishes that the implementer passed the expressly forbidden
`--integration` flag. The invoked oracle returned `M1E_NOT_AUTHORIZED` with exit 77 before DSN read,
driver import, socket, subprocess, database access, Alembic, DDL rendering/execution, or byte mutation.
That containment is preserved as evidence; it is not a waiver. The original authorization is consumed.
Its bound `2572e4ab858842ea272648d223c4cb503d8f8bfa1a123bb9680653211219532f`
byte identity is the trailing-whitespace-only normalization of prior identity
`df4afae478a399d5748710bb66089b405f2513dd4000a131e1b0c9880e4504f0`; the procedural findings,
containment, required recovery gate, and verdict are unchanged.

## 2. Frozen seven-file subject

Acceptance may concern only these exact bytes. The acceptance operator must recompute every digest
before any other permitted check and again immediately before issuing a verdict.

| # | Path | Required SHA-256 |
|---:|---|---|
| 1 | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

No candidate byte may be edited. A changed digest, an eighth implementation path, a generated cache
or artifact inside the repository, or a need to repair any finding is a hard stop requiring a new
candidate, new authorization, independent review, and fresh owner activation.

## 3. Exact recovery scope

After a different agent has independently reviewed this exact authorization and issued `PASS`, and
after the owner has activated its exact hash within the expiring window, the named acceptance
operator may only:

1. recompute and compare the hashes in sections 1 and 2;
2. inspect `git status`, `git diff --check`, and the textual diff limited to the seven candidate paths;
3. parse the two migration Python sources and static oracle with Python `ast.parse` or in-memory
   `compile()` without importing them and without writing bytecode;
4. parse the two JSON candidates with the Python standard-library JSON parser;
5. perform `bash -n ai-stack/migrations/test-migrations.sh`;
6. run `python3 scripts/testing/test-workflow-shadow-migration.py` with **no arguments**, only after
   re-verifying its bound hash; and
7. use read-only text search to verify the frozen branch, authority, connection/process, destructive,
   secret, and runtime-adoption constraints from the original authorization.

The top-level tools needed for those seven static operations are the entire command allowlist. The
candidate oracle must remain in its default offline/static mode and must launch no child process. No
environment variable, alternate argument, wrapper, shell indirection, retry, generated test, or
equivalent command may expand that allowlist. The operator may write only a new review record in this
plan directory; it may not stage or commit.

The prior exact-byte evidence recorded under the procedural stop—default static oracle `PASS`, static
compilation/parsing `PASS`, Bash syntax `PASS`, `aq-qa 0 --machine` `PASS`, and Tier-0 `PASS`—may be
cited by hash. This recovery grant does **not** authorize rerunning `aq-qa`, Tier-0, Phase-0, or any
broader runner because they can execute non-subject commands. Exact-byte identity is the evidence
bridge; it does not transform static evidence into database evidence.

## 4. Explicit prohibitions and hard stops

The acceptance operator must stop immediately, issue no `PASS`, and report the exact attempted or
observed condition if any of the following occurs:

- any candidate or bound-evidence byte/hash drift;
- `--integration`, `--dsn-file`, an M1E token, another argument, or an environment-provided execution
  path is passed to the oracle;
- any Alembic command or API, including online execution, offline mode, SQL rendering, history,
  heads, upgrade, downgrade, stamp, or revision;
- database/client/driver/DSN access, DNS, socket, network, child subprocess, `psql`, SQLAlchemy engine,
  or PostgreSQL read/write;
- Nix evaluation, build, activation, deployment, service action, runtime hook, traffic, cutover, or
  dashboard/operational claim;
- Python import/execution of either migration source, bytecode/cache generation, repository write
  outside the one review record, candidate staging, or candidate commit by the reviewer;
- a need to edit, normalize, format, regenerate, relax, reinterpret, or add any candidate path; or
- a claim that DDL, branch resolution, grants, rollback, database health, migration readiness, or
  M1E behavior was dynamically proven.

There is no exception for a fail-closed result: invoking a prohibited path consumes this single-use
grant and forces another procedural recovery.

## 5. Required independent acceptance and commit boundary

The acceptance operator must be independent of the candidate implementation and of this authorization
author. Its review record must bind:

- this authorization's activated SHA-256 and owner activation window;
- the exact seven hashes before and after the static checks;
- the procedural-stop record and original consumed authorization hashes;
- every command actually run, its exit status, and confirmation that no unlisted command ran;
- explicit confirmation of no candidate edit, import, bytecode, integration flag, Alembic, database,
  socket, child subprocess, Nix evaluation/deployment, runtime adoption, or operational claim; and
- one verdict: `PASS`, `REQUEST_REVISION`, or `FAIL`.

Only an exact-byte `PASS` permits the orchestrator—not the reviewer—to stage and commit the seven
candidate paths with the recovery authorization, its authorization review, the fresh acceptance
record, and the existing procedural-stop record. The orchestrator must recheck all hashes immediately
before staging and immediately before commit. Any drift or prohibited invocation voids the verdict.

Commit acceptance remains static artifact acceptance only. Legacy `workflow-sessions.json` remains
the sole live authority. M1E, database connectivity, DDL render/execution, grants, runtime adoption,
traffic, cutover, cleanup, rollback, and all later B2 slices remain unauthorized.

## 6. Activation record

Current activation state: **NOT ACTIVATED**.

Before owner activation, an independent reviewer must issue `PASS` on this exact authorization hash.
The later owner statement must name:

- this document's exact SHA-256;
- `codex-subagent-b2-m1a-recovery-acceptance`;
- an activation timestamp and an expiry no more than 24 hours later; and
- confirmation that the seven hashes, static-only command allowlist, no-edit rule, and every hard stop
  remain unchanged.

`RECORD: PREPARED_ONLY. This document authorizes no action until independently reviewed and explicitly
activated by the owner. Candidate editing, integration mode, Alembic, database/client/socket/subprocess
activity, Nix evaluation/deployment, runtime adoption, M1E, and later B2 slices remain unauthorized.`
