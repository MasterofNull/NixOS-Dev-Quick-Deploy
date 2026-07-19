# Foundation B2-M1A amendment 1 design and authorization review

**Review date:** 2026-07-19 UTC
**Reviewer:** Codex sub-agent `/root/b2_m1a_am1_auth_review`
**Roles:** independent architecture, security, SRE, scope, and authorization reviewer
**Review type:** exact-byte design and inactive-authorization gate; no implementation or candidate acceptance
**Overall verdict:** **PASS**

## 1. Exact reviewed subjects

| Subject | Recomputed SHA-256 | Verdict |
|---|---|---|
| `B2-M1A-AM1-DESIGN-PACKET.md` | `7c799909421c73aa276a45d266d9abcd52f45ff58feebde2f2733672923322c3` | **PASS** |
| `B2-M1A-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `3e4cd79ab7ad67b3f627373cfbd8f4ec71d5a9429e3795f48767d316dc6a573e` | **PASS** |

Any subject-byte change invalidates this review.

## 2. Recovery and predecessor bindings

The authorization accurately preserves the material lineage rather than waiving it:

- recovery acceptance SHA-256
  `813ef2ad5eeaf69c94efddadadfb5e8ba196d642d8955496d62981b17e1e846a` remains
  `REQUEST_REVISION` for incomplete source-to-policy coverage and non-exact recovery command
  discipline;
- procedural-stop acceptance SHA-256
  `2572e4ab858842ea272648d223c4cb503d8f8bfa1a123bb9680653211219532f` remains
  `REQUEST_REVISION` after the contained but prohibited `--integration` invocation;
- the original consumed implementation authorization remains bound at SHA-256
  `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906`;
- the consumed recovery authorization remains bound at SHA-256
  `b8455788464bd22f261e0e5254c1cc3bce2f7af3b881cf2cd92eb0ce77da4b3a`;
- all four historical design-review identities and verdicts match their repository bytes; and
- accepted B2-C1 Git commit `8e285cdd978f2fc020393ac4327747f3e8f31476` remains in the lineage.

The design was prepared against Git commit `53740c44fe590ac98f019918b99bbfd467feccb7`, which is an
ancestor of the reviewed worktree HEAD. The seven predecessor hashes were independently recomputed
and match exactly. In particular, only `scripts/testing/test-workflow-shadow-migration.py` is marked
mutable; the other six candidate paths remain frozen.

## 3. One-file ceiling and coverage sufficiency

The one-file ceiling is sufficient and exact. The existing static oracle already reads the dormant
B2 migration, privilege policy, Nix caller, canonical migration test, and validation registry, and it
already names the existing AIDB migration path. Closing the recovery findings therefore requires
only stronger pure parsing and comparisons inside that oracle. No policy, migration, Nix, registry,
shell, runtime, dashboard, or additional fixture change is necessary.

The amendment closes every substantive recovery omission:

1. It requires AST-level, literal, unique validation of the AIDB revision, parent, exact
   `("aidb",)` branch-label tuple, and `depends_on`, without import, execution, or bytecode.
2. It closes delivery and reader privilege objects by exact equality across schema, tables, and the
   empty function cell, rejecting extra keys, objects, actions, or privileges.
3. It binds the exact function, trigger, index, constraint, and foreign-key policy identities to
   their corresponding migration relationships rather than accepting counts or free-standing name
   presence.
4. It retains the policy byte digest, making the new semantic binding additive rather than a weaker
   replacement.
5. It requires in-memory negative mutations for every repaired class while prohibiting fixture or
   repository writes, migration imports, and child processes.

The named policy objects and corresponding dormant migration forms exist in the frozen inputs, so
these requirements are implementable within the sole mutable test file. The mandatory
`SCOPE_EXPANSION_REQUIRED` stop correctly prevents an implementer from compensating through a second
file or weaker assertion.

## 4. Operation, security, and truth-boundary review

The literal operation contract is usable and bounded. It permits only path-bounded reads/searches,
exact hashing and path-limited diffs, `apply_patch` on the sole mutable file, one no-argument oracle
execution per iteration, and one in-memory AST syntax check. It expressly excludes discovery/help,
session and skill-selection commands, broad runners, wrappers, alternate arguments, environment
overrides, generated files, bytecode, and shell indirection. The task therefore must preload the
listed paths, hashes, skill names, and allowlist exactly as the authorization requires.

The stop contract is fail closed and preserves the lessons from both consumed grants. Passing
`--integration`, using an unlisted operation, observing a digest mismatch, needing another path, or
touching Alembic, a database/DSN/driver, socket/network/subprocess, Nix, deployment, M1E, staging, or
commit consumes the activation and requires a new incident/recovery path. No harmless-command or
fail-closed-execution exception remains.

The evidence language is truthful: success proves only deterministic static artifact consistency.
Legacy `workflow-sessions.json` remains the sole live authority, and the package makes no claim about
Alembic branch resolution, PostgreSQL syntax, applied DDL, grants, rollback, database health,
migration readiness, runtime adoption, or M1E behavior.

## 5. Activation and acceptance gates

The authorization remains `PREPARED_ONLY`, single-use, hash-bound, and assigned only to
`codex-subagent-b2-m1a-am1-implementer`. It requires explicit owner activation of its exact SHA-256,
with a named activation timestamp and expiry no more than 24 hours later. Implementation cannot
self-accept: a different independent acceptance reviewer must receive a newly frozen seven-hash
subject under its own prepared, independently reviewed, owner-activated static-acceptance
authorization. M1E and all live or operational activity remain separately unauthorized.

No candidate or reviewed-subject byte was edited, executed, staged, or committed during this review.

VERDICT: PASS — the exact amendment design and PREPARED_ONLY authorization bind the complete rejection lineage and predecessor hashes, close all identified static source-to-policy gaps within an exact one-file ceiling, provide a usable literal operation allowlist and fail-closed stop contract, and preserve independent acceptance plus the no-connectivity/no-runtime boundary
