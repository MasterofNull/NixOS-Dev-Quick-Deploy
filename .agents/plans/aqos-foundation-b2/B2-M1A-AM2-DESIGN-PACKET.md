# Foundation B2-M1A amendment 2 design packet

**Slice:** B2-M1A-AM2 — workflow-compatible static-oracle repair
**Status:** **PREPARED_ONLY — DESIGN NOT ACTIVATED**
**Prepared date:** 2026-07-19 UTC
**Prepared against Git commit:** `d07f08dc0be875b9cc984fe424ec405ca2492913`
**Supersedes for execution:** B2-M1A-AM1 only; its accepted oracle requirements remain normative
**Incident:** `B2-M1A-AM1-WORKFLOW-CONFLICT-INCIDENT.md` at SHA-256
`854733d2b7567336576d16e5ba092da3a034d764f8d9830d2fe4ee12644b0edc`
**Revision-1 independent review:** `B2-M1A-AM2-AUTHORIZATION-REVIEW.md` at SHA-256
`b5c8afde8746f85034d76249e13151eabe8b53a6ca6280adf0082e854c5d542e`;
`REQUEST_REVISION` for missing governance event/projection authority

This packet repairs the AM1 authorization/workflow contradiction without widening the candidate or
runtime boundary. It grants no implementation, acceptance, staging, commit, database, Alembic, Nix,
deployment, runtime, or later-slice authority.

## 1. Objective and accepted requirement inheritance

B2-M1A-AM1's one-file source-to-policy repair remains technically sufficient and unchanged. AM2
inherits every requirement in `B2-M1A-AM1-DESIGN-PACKET.md` at SHA-256
`7c799909421c73aa276a45d266d9abcd52f45ff58feebde2f2733672923322c3`, including:

1. literal AST validation of the existing AIDB revision and exact `("aidb",)` branch label;
2. closed delivery and reader privilege objects across schema, tables, and functions;
3. exact function, trigger, index, constraint, and foreign-key source relationship binding;
4. retention of the policy byte digest;
5. pure in-memory negative mutations for every repaired class; and
6. deterministic, standard-library-only, no-argument, offline truth language.

AM2 changes only the operation envelope. It distinguishes mandatory read-only control-plane
orientation from prohibited data-plane activity so an implementer can comply with both the grant and
the repository workflow.

## 2. Frozen seven-file subject and one-file correction ceiling

Every digest must match before any candidate edit. Only row 5 may change.

| # | Operation | Path | Required predecessor SHA-256 |
|---:|---|---|---|
| 1 | FROZEN | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | FROZEN | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | FROZEN | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | FROZEN | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | MODIFY | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | FROZEN | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | FROZEN | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

The sole **implementation-candidate** write is an `apply_patch` edit to row 5 implementing the
inherited AM1 section 3 repair. Canonical governance events and their projections, defined in
section 3, are monitoring evidence outside the candidate ceiling. A need for any second candidate
path, fixture, policy, migration, Nix, registry, shell, or generated product is
`SCOPE_EXPANSION_REQUIRED` and stops the attempt before that write.

## 3. Mandatory workflow-compatible control-plane envelope

The implementation authorization must explicitly permit the following governance operations without
counting their event/projection paths as implementation candidates:

1. accept the orchestrator's completed `aq-session-start` hydration for this shared task and read the
   resulting session context; if the delegated execution environment is a distinct session that has
   not inherited that evidence, run exactly one `aq-session-start --task "implement B2-M1A-AM2
   static oracle repair"` before any candidate edit;
2. read `.agent/collaboration/RESUME.json`, then emit the phase-start RESUME update through the exact
   `aq-event resume` invocation frozen by the authorization;
3. read the exact selected skills `.agent/skills/slice-authoring/SKILL.md` and
   `.agent/skills/testing-patterns/SKILL.md`; selection is performed by the orchestrator, so no
   autonomous skill selection or unrelated skill expansion is needed;
4. use bounded `lean-ctx read`, `lean-ctx grep`, `lean-ctx bypass` for an already-bounded read, or
   `sed -n` only on the documents, skills, and seven candidate paths explicitly named by the grant;
5. use bounded `rg -n`, `sha256sum`, and path-restricted `git status`/`git diff` only on those paths;
   and
6. before the candidate edit, create the bounded intent record through the authorization's literal
   `pending-update add` invocation; after the candidate write, emit the literal `aq-event pulse`;
7. at slice completion or mandatory stop, close the intent and update HANDOFF through exactly one
   authorized `pending-update done`, `partial-success`, or `failed` invocation and emit the matching
   terminal pulse; and
8. run only the exact static oracle, syntax compilation, and JSON-parse validations named by the
   grant.

The following are non-candidate governance event/projection evidence only:

- `.agents/events/a2a-events.jsonl`;
- `.agent/collaboration/RESUME.json`;
- `.agent/collaboration/PENDING.json`;
- `.agent/collaboration/PULSE.log`;
- `.agent/collaboration/HANDOFF.md`; and
- a session-context file produced by the one conditionally permitted `aq-session-start` invocation.

No agent may edit those paths with `apply_patch`, a text editor, shell redirection, or arbitrary
content. Only `aq-session-start`, `aq-event`, and `scripts/ai/lib/pending-update` with the literal
arguments frozen in the authorization may mutate them. Those writers may perform their normal
atomic replacement, append, projection, bounded decay, timestamp, and event-ID behavior. Their
internal writes are terminal governance emissions and do not recursively require another pulse.

`aq-prime`, broad health probes, recursive file listings, unbounded repo search, network research,
and broad status/diff remain unnecessary and unauthorized for this frozen repair. A read-only
prerequisite outside the explicit envelope is a stop requesting authorization correction, not an
excuse to proceed.

## 4. Exact static validation design

The authorization must allow, and the implementer must report, only these executable validations:

1. `python3 scripts/testing/test-workflow-shadow-migration.py` with no arguments;
2. an in-process `py_compile.compile(..., doraise=True)` syntax check of the sole mutable oracle,
   writing its compiled artifact only to a named `/tmp` path outside the repository;
3. an in-process standard-library JSON parse of exactly
   `config/workflow-shadow-db-privileges.json` and `config/validation-check-registry.json`;
4. `git diff --check -- scripts/testing/test-workflow-shadow-migration.py`; and
5. before/after `sha256sum` plus path-restricted status/diff for the seven-file subject.

The `/tmp` compile artifact is validation evidence, not a repository candidate or retained product.
The implementer must not create `__pycache__`, `.pyc`, fixtures, snapshots, product logs, or generated
files inside the repository. The exact governance event/projection evidence in section 3 is the sole
exception and is not product output. No shell, migration, Nix, QA, Phase-0, Tier-0, or live-system
runner is part of this implementation validation.

## 5. Absolute prohibitions and mandatory stops

AM2 preserves the AM1 truth boundary. The implementer must not invoke or access:

- `--integration`, `--dsn-file`, an M1E token, alternate oracle arguments, or environment-provided
  execution paths;
- Alembic in any command, API, migration, history, current, heads, upgrade, downgrade, check, or
  offline-render mode;
- migration import or execution, database client/driver/DSN, PostgreSQL, SQL/DDL execution or render,
  DNS, socket, network, subprocess, or child process;
- Nix evaluation/build/activation, service or runtime action, deployment, traffic, cutover,
  dashboard claim, cleanup, rollback, or M1E;
- broad `aq-qa`, Phase-0, Tier-0, full repository test, or deployment validation by the implementer;
- candidate edits beyond row 5, non-governance repository cache/generated artifacts, direct or
  arbitrary governance-path edits, staging, commit, destructive Git, deletion, archive, or authority
  expansion; or
- claims that static success proves Alembic resolution, PostgreSQL syntax, applied DDL, grants,
  rollback, database health, schema readiness, runtime adoption, or migration readiness.

Any prohibited attempt, predecessor mismatch, frozen-row drift, or need for a second candidate path
consumes the activation and requires a new incident/recovery design even if it fails closed.

## 6. Gates and binary acceptance criteria

Before implementation:

1. an independent architecture/security/SRE reviewer who did not author AM2 must issue exact-byte
   `PASS` on this design;
2. a single-use PREPARED_ONLY authorization must bind this design, the incident, AM1
   design/authorization/review, and all seven predecessor hashes;
3. an independent reviewer must issue exact-byte `PASS` on that authorization; and
4. the owner must activate the authorization's exact SHA-256, name the required implementer, and set
   an expiry no more than 24 hours after activation.

Implementation acceptance is binary only if all are true:

- every inherited AM1 source-to-policy assertion and negative mutation class is implemented in row 5;
- the other six candidate paths retain their exact predecessor hashes;
- only the explicitly permitted orientation, canonical governance event/projection, candidate-write,
  and static-validation envelope was used;
- the default static oracle, exact syntax compile, JSON parse, and whitespace checks pass;
- the implementation makes no live-readiness claim and leaves legacy JSON authoritative;
- an independent acceptance reviewer binds the new seven-file hashes and issues `PASS` under a
  separately prepared and activated acceptance grant; and
- RESUME, intent/PENDING, post-write PULSE, and finish/stop HANDOFF evidence was emitted only through
  the exact canonical writers, with no arbitrary governance-path edit; and
- **the AM2 authorization is explicitly found consistent with mandatory `AGENTS.md` and
  `.agent/WORKFLOW-CANON.md` session, RESUME, intent, skill-read, search-before-edit, PULSE,
  HANDOFF, validation, and monitoring prerequisites.**

M1E and all live or operational activity remain separately unauthorized.

`RECORD: PREPARED_ONLY. This design authorizes no implementation or acceptance action.`
