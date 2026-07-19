# Foundation B2-M1A amendment 1 implementation authorization

**Authorization ID:** `auth-aqos-foundation-b2-m1a-am1-20260719`
**Status:** **PREPARED_ONLY — NOT ACTIVATED**
**Prepared date:** 2026-07-19 UTC
**Prepared against Git commit:** `53740c44fe590ac98f019918b99bbfd467feccb7`
**Required implementer on activation:** `codex-subagent-b2-m1a-am1-implementer`
**Single use:** one implementation attempt against the exact one-file ceiling below
**Expiry rule:** owner activation must name this document's exact SHA-256, the required implementer,
an activation timestamp, and an expiry no more than 24 hours later.

This authorization has no effect until its design and this exact authorization have each received an
independent `PASS`, followed by explicit owner activation. It does not reactivate the original or
recovery grants and does not authorize acceptance of its own output.

## 1. Immutable evidence lineage

Any mismatch is a hard stop before editing.

| Subject | Bound identity |
|---|---|
| amendment design, `B2-M1A-AM1-DESIGN-PACKET.md` | SHA-256 `7c799909421c73aa276a45d266d9abcd52f45ff58feebde2f2733672923322c3` |
| blocking recovery acceptance, `B2-M1A-RECOVERY-ACCEPTANCE.md` | SHA-256 `813ef2ad5eeaf69c94efddadadfb5e8ba196d642d8955496d62981b17e1e846a`; `REQUEST_REVISION` |
| prior procedural-stop acceptance, `B2-M1A-IMPLEMENTATION-ACCEPTANCE.md` | SHA-256 `2572e4ab858842ea272648d223c4cb503d8f8bfa1a123bb9680653211219532f`; `REQUEST_REVISION` |
| original consumed implementation authorization, `B2-M1-IMPLEMENTATION-AUTHORIZATION.md` | SHA-256 `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906` |
| accepted design, `B2-M1-DESIGN-PACKET.md` | SHA-256 `020462d0ec3222bc893c7543712856a80ce8acb92b5b9caa48ab3a902e1860aa` |
| design review revision 1 | SHA-256 `ed816d7d02c237216ffb85678dc16b03fc07429eef19d75afd8d20a809fc30f4`; `REQUEST_REVISION` |
| design review revision 2 | SHA-256 `26e3fad6d524d2d88d39ec0eedb63a1f083109260b1160a45d6def827603a052`; `REQUEST_REVISION` |
| design review revision 3 | SHA-256 `09e994c8f7fa7e9df11f0b00d412d7304d523187568e61bce8a3c95483d085f1`; `PASS` |
| design review revision 4 | SHA-256 `84cd8a5b2f8e5d272c548c40e0fe02e50d53333a2a13f57aa84f6e30ac16a6ce`; `PASS` |
| consumed recovery authorization, `B2-M1A-ACCEPTANCE-RECOVERY-AUTHORIZATION.md` | SHA-256 `b8455788464bd22f261e0e5254c1cc3bce2f7af3b881cf2cd92eb0ce77da4b3a` |
| initial recovery-authorization review | SHA-256 `ec70f3290a188679dc5731052e0b33ac992dc2b70eec6b1b5481387fbbed0b71`; stale historical review |
| rebound recovery-authorization review | SHA-256 `555b14c7fe540c37d9c70c4679c75995f1af4acef595f90f5c5faec57541f984`; `PASS` |
| accepted B2-C1 implementation | Git `8e285cdd978f2fc020393ac4327747f3e8f31476` |

The original authorization was consumed by a prohibited `--integration` invocation that failed
closed before DSN, driver, socket, subprocess, database, Alembic, DDL, or byte mutation. The recovery
authorization was then consumed by an independent `REQUEST_REVISION` finding that the static oracle
did not close its promised source-to-policy contract. Those findings are preserved, not waived.

## 2. Exact seven-file predecessor and one-file ceiling

The implementer must recompute all seven digests before any edit. Only row 5 may change.

| # | Operation | Path | Required predecessor SHA-256 |
|---:|---|---|---|
| 1 | FROZEN | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | FROZEN | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | FROZEN | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | FROZEN | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | MODIFY | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | FROZEN | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | FROZEN | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

The only permitted mutation is the amendment design section 3 repair in row 5. `apply_patch` is the
only permitted write mechanism. No generated file, cache, fixture, formatting-only change, or second
candidate path is allowed. A need to change any frozen row or another path requires an immediate
`SCOPE_EXPANSION_REQUIRED` stop and a new design.

## 3. Exact implementation requirements

The implementer must satisfy every requirement in `B2-M1A-AM1-DESIGN-PACKET.md` without weakening
existing checks. In particular, row 5 must:

1. AST-parse and exactly validate the existing AIDB revision identity and literal one-element
   `("aidb",)` branch-label tuple without importing or executing it;
2. compare the complete delivery and reader grant objects, including exact `schema`, `tables`, and
   empty `functions` cells;
3. compare the exact policy function, trigger, index, constraint, and foreign-key identities to their
   corresponding table/column/function relationships in the dormant B2 migration source;
4. retain the exact policy byte-digest binding;
5. keep the oracle standard-library-only, deterministic, no-argument, and offline; and
6. include pure in-memory negative mutation checks for every repaired class while writing no fixture.

Substring presence by itself cannot satisfy relationship binding. The assertions must reject missing,
extra, substituted, duplicated, or wrongly attached identities. The final no-argument output must
remain truthful static-only evidence:

```text
B2-M1A static oracle: PASS; authority=legacy_json_authoritative coverage=migration_artifacts_static_only
```

## 4. Entire permitted operation and command contract

The orchestrator must place the authorization, design, predecessor hashes, relevant file paths,
accepted skill names, and this allowlist directly in the implementer's task. The implementer must not
run an orientation, discovery, help, command-listing, session-hydration, skill-selection, or file-list
command. There is no implied harmless-command exception.

The following operations are the entire allowance. Paths are limited to the two amendment documents,
the evidence-lineage documents in section 1, the seven rows in section 2, and the two read-only skill
files `.agent/skills/slice-authoring/SKILL.md` and `.agent/skills/testing-patterns/SKILL.md`:

| Primitive | Exact permitted use |
|---|---|
| `sed -n` or repository read tool | bounded read of the explicitly listed paths only |
| `rg -n` | search for the exact branch, grant, function, trigger, index, constraint, foreign-key, import, integration, process, network, database, Nix, and authority tokens within the seven candidate paths only |
| `sha256sum` | hash the exact evidence and seven candidate paths bound here, before edit and after validation |
| `git status --short -- <paths>` | status limited to the seven candidate paths and the two amendment documents |
| `git diff --check -- scripts/testing/test-workflow-shadow-migration.py` | whitespace check for the sole mutable file |
| `git diff -- scripts/testing/test-workflow-shadow-migration.py` | textual diff for the sole mutable file |
| `apply_patch` | edit only `scripts/testing/test-workflow-shadow-migration.py` |
| `python3 scripts/testing/test-workflow-shadow-migration.py` | exactly once per implementation iteration, with no arguments, wrapper, environment override, retry harness, or alternate entry point |
| `python3 -c` | one in-memory `ast.parse` syntax check of row 5; it may read only row 5 and must not import it or write bytecode |

No other executable, flag, argument, environment override, shell indirection, glob expansion, helper,
wrapper, or equivalent operation is authorized. In particular, `rg --files`, `find`, `ls`, `help`,
`--help`, `aq-prime`, `aq-resume`, `aq-session-start`, `aq-skill-auto`, `aq-skill-suggest`, broad
`git status`, broad `git diff`, `py_compile`, and compileall are not permitted. If required project
orientation cannot be completed through the preloaded task and bounded reads above, stop before edit.

The implementer must record every operation actually used and its result for the acceptance handoff.

## 5. Prohibitions and mandatory stops

The implementer must stop immediately, make no further candidate edit, and report the exact condition
if any of the following occurs:

- an evidence or predecessor digest mismatch, an eighth candidate path, or any frozen-row drift;
- a need to edit anything other than row 5 or use a command outside section 4;
- `--integration`, `--dsn-file`, an M1E token, another oracle argument, or an environment-provided
  execution path;
- Alembic command/API, migration import/execution, offline SQL rendering, SQL/DDL execution,
  database client/driver/DSN access, DNS, socket, network, child subprocess, or PostgreSQL access;
- Nix evaluation/build/activation, service action, deployment, traffic, cutover, runtime hook,
  dashboard claim, broad QA, Phase-0, Tier-0, cleanup, rollback, or M1E behavior;
- bytecode/cache/generated-file creation, staging, commit, destructive Git, deletion, or archive; or
- any claim that static success proves branch resolution, PostgreSQL syntax, applied DDL, grants,
  rollback, database health, migration readiness, or operational adoption.

There is no fail-closed exception. A prohibited attempt consumes the single-use activation and
requires a new incident/recovery path even if it returns before a side effect.

## 6. Required evidence and independent acceptance

The implementer handoff must include:

- the activated authorization hash and owner activation window;
- before/after hashes for all seven candidate paths, with change only in row 5;
- exact operation log under section 4;
- default oracle `PASS` and in-memory syntax/mutation evidence;
- path-limited diff and whitespace evidence;
- explicit confirmation of no integration argument, migration import/execution, Alembic, database,
  DSN, driver, network, socket, subprocess, bytecode, Nix, broad runner, deployment, staging, commit,
  runtime action, or authority expansion; and
- a statement that legacy `workflow-sessions.json` remains sole live authority.

After implementation, an independent reviewer who did not author this design, authorization, or
candidate must receive a new exact seven-hash subject and issue `PASS`, `REQUEST_REVISION`, or `FAIL`.
The reviewer receives its own separately prepared, independently reviewed, and owner-activated
static-acceptance authorization with a literal operation allowlist. The implementation activation
does not authorize candidate acceptance. Only independent `PASS` allows the orchestrator to stage
and commit the accepted bounded package.

M1E, database connectivity, DDL render/execution, grants, runtime adoption, deployment, traffic,
cutover, cleanup, rollback, and every later B2 slice remain unauthorized.

## 7. Activation record

Current activation state: **NOT ACTIVATED**.

Before activation:

1. an independent reviewer must issue `PASS` on design SHA-256
   `7c799909421c73aa276a45d266d9abcd52f45ff58feebde2f2733672923322c3`;
2. an independent reviewer must issue `PASS` on this exact authorization hash; and
3. the owner must then name this exact authorization SHA-256,
   `codex-subagent-b2-m1a-am1-implementer`, an activation timestamp, and an expiry no more than 24
   hours later, confirming the one-file ceiling and all stop conditions remain unchanged.

`RECORD: PREPARED_ONLY. This document authorizes no action until independently reviewed and explicitly
activated by the owner. Candidate acceptance, M1E, database/Alembic/DDL activity, Nix/deployment,
runtime adoption, staging, commit, and later B2 slices remain unauthorized.`
