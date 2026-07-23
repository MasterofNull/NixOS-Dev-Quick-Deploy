# Foundation B2-M1A amendment 2 implementation authorization

**Authorization ID:** `auth-aqos-foundation-b2-m1a-am2-20260719`
**Status:** **PREPARED_ONLY — NOT ACTIVATED**
**Prepared date:** 2026-07-19 UTC
**Prepared against Git commit:** `d07f08dc0be875b9cc984fe424ec405ca2492913`
**Required implementer on activation:** `codex-subagent-b2-m1a-am2-implementer`
**Single use:** one implementation attempt against the exact one-file ceiling below
**Expiry rule:** owner activation must name this document's exact SHA-256, the required implementer,
an activation timestamp, and an expiry no more than 24 hours later.

This authorization has no effect until the AM2 design and this exact authorization each receive an
independent `PASS`, followed by explicit owner activation. It does not reactivate AM1, authorize its
own acceptance, or grant any live, database, migration, Nix, deployment, or later-slice authority.

## 1. Immutable evidence and governance lineage

Any mismatch is a hard stop before candidate editing.

| Subject | Bound identity |
|---|---|
| AM2 design revision 2, `B2-M1A-AM2-DESIGN-PACKET.md` | SHA-256 `9b50fa84889c3c04ac4e38b0aab844c3571f1c258ad6b99cbc7536d70c251ba9` |
| AM2 revision-1 independent review, `B2-M1A-AM2-AUTHORIZATION-REVIEW.md` | SHA-256 `b5c8afde8746f85034d76249e13151eabe8b53a6ca6280adf0082e854c5d542e`; retained `REQUEST_REVISION` history |
| AM1 workflow-conflict incident, `B2-M1A-AM1-WORKFLOW-CONFLICT-INCIDENT.md` | SHA-256 `854733d2b7567336576d16e5ba092da3a034d764f8d9830d2fe4ee12644b0edc`; `CONTAINED` |
| accepted AM1 design, `B2-M1A-AM1-DESIGN-PACKET.md` | SHA-256 `7c799909421c73aa276a45d266d9abcd52f45ff58feebde2f2733672923322c3` |
| consumed AM1 authorization, `B2-M1A-AM1-IMPLEMENTATION-AUTHORIZATION.md` | SHA-256 `3e4cd79ab7ad67b3f627373cfbd8f4ec71d5a9429e3795f48767d316dc6a573e` |
| AM1 design/authorization review, `B2-M1A-AM1-AUTHORIZATION-REVIEW.md` | SHA-256 `b0cd50f5c40739d7fd36541208e1a0a1c0ac8831391bae2db66b5dcf77ea4f53`; historical `PASS` superseded for activation fitness by the incident |
| project instructions, `AGENTS.md` | SHA-256 `1e1019757d035f9934839c6d71a7c8981c70ca29b7dec436b47a95aa686b29b2` |
| workflow SSOT, `.agent/WORKFLOW-CANON.md` | SHA-256 `8775c67fa415a6f3a9be6d66597aa911c8017f817633cbb9cb0684450fa51e4a` |
| blocking recovery acceptance, `B2-M1A-RECOVERY-ACCEPTANCE.md` | SHA-256 `813ef2ad5eeaf69c94efddadadfb5e8ba196d642d8955496d62981b17e1e846a`; `REQUEST_REVISION` |
| prior procedural-stop acceptance, `B2-M1A-IMPLEMENTATION-ACCEPTANCE.md` | SHA-256 `2572e4ab858842ea272648d223c4cb503d8f8bfa1a123bb9680653211219532f`; `REQUEST_REVISION` |
| original consumed implementation authorization, `B2-M1-IMPLEMENTATION-AUTHORIZATION.md` | SHA-256 `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906` |
| consumed recovery authorization, `B2-M1A-ACCEPTANCE-RECOVERY-AUTHORIZATION.md` | SHA-256 `b8455788464bd22f261e0e5254c1cc3bce2f7af3b881cf2cd92eb0ce77da4b3a` |
| accepted B2-C1 implementation | Git `8e285cdd978f2fc020393ac4327747f3e8f31476` |

The incident proves AM1 was consumed before candidate editing because its operation contract
contradicted mandatory workflow. AM2 preserves AM1's technical requirements and repairs only that
control-plane defect. No prior rejection or procedural stop is waived.

## 2. Exact seven-file predecessor and one-file ceiling

The implementer must recompute all seven hashes before any candidate edit. Only row 5 may change.

| # | Operation | Path | Required predecessor SHA-256 |
|---:|---|---|---|
| 1 | FROZEN | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | FROZEN | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | FROZEN | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | FROZEN | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | MODIFY | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | FROZEN | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | FROZEN | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

The only permitted implementation-candidate mutation is `apply_patch` on row 5 to implement every
inherited AM1 design section 3 requirement. The canonical governance events and projections in
section 4 are evidence outside this candidate ceiling. A second candidate path, generated product
artifact, or frozen-row drift is an immediate `SCOPE_EXPANSION_REQUIRED` stop.

## 3. Mandatory read-only orientation allowance

These orientation prerequisites are expressly authorized and do not consume the candidate mutation:

1. rely on the orchestrator's already completed `aq-session-start` for this shared task and read its
   generated session context; if the delegate is a distinct non-hydrated session, run exactly once:
   `aq-session-start --task "implement B2-M1A-AM2 static oracle repair"` before candidate editing;
2. read `.agent/collaboration/RESUME.json`; its phase-start update is separately required by section 4;
3. read exactly `.agent/skills/slice-authoring/SKILL.md` and
   `.agent/skills/testing-patterns/SKILL.md`, the skills preselected by the orchestrator;
4. bounded-read the three AM2 documents, the AM1 design/authorization/review, evidence-lineage
   records named in section 1, `AGENTS.md`, `.agent/WORKFLOW-CANON.md`, and the seven candidate paths;
5. use `lean-ctx read`/`lean-ctx grep` or `sed -n` for those bounded reads, `rg -n` for exact source
   tokens within those paths, and `sha256sum` for those exact paths; and
6. use `git status --short -- <authorized paths>`,
   `git diff --check -- scripts/testing/test-workflow-shadow-migration.py`, and
   `git diff -- scripts/testing/test-workflow-shadow-migration.py` only.

The conditional `aq-session-start` may create its normal single
`.agents/scratchpad/session-context-*.md` hydration record; that record is governance evidence, not a
candidate. No broad repository status/diff/search, recursive path discovery, network research,
autonomous skill selection, or unrelated orientation is authorized. If another prerequisite is
genuinely mandatory, stop before edit and return `AUTHORIZATION_WORKFLOW_CONFLICT` rather than
silently use it.

## 4. Exact governance event and projection allowance

The following five paths, plus the append-only event log, are non-candidate governance evidence:

- `.agent/collaboration/RESUME.json`;
- `.agent/collaboration/PENDING.json`;
- `.agent/collaboration/PULSE.log`;
- `.agent/collaboration/HANDOFF.md`;
- the conditional session-context record from section 3; and
- `.agents/events/a2a-events.jsonl`.

They may change only through the following literal canonical-writer operations. Arbitrary content,
direct `apply_patch`, text-editor writes, shell redirection, alternate arguments, and environment
overrides are prohibited.

### 4.1 Phase start and intent, before candidate editing

Run exactly once:

```text
scripts/ai/aq-event resume --agent codex-subagent-b2-m1a-am2-implementer --objective "Implement B2-M1A-AM2 one-file static oracle repair" --phase "B2-M1A-AM2 implementation" --hint "Preserve offline static-only authority; stop on any scope or connectivity expansion" --todo "Edit only scripts/testing/test-workflow-shadow-migration.py"
```

Then run exactly once:

```text
python3 scripts/ai/lib/pending-update add b2-m1a-am2-20260719 codex-subagent-b2-m1a-am2-implementer scripts/testing/test-workflow-shadow-migration.py "Implement B2-M1A-AM2 one-file static oracle repair"
```

These operations provide the phase-start RESUME projection, append-only event, bounded PENDING intent,
and initial HANDOFF evidence required by the governing workflow.

### 4.2 Candidate-write pulse

Immediately after the single successful `apply_patch` candidate write, run exactly once:

```text
scripts/ai/aq-event pulse --agent codex-subagent-b2-m1a-am2-implementer --action write --scope scripts/testing/test-workflow-shadow-migration.py --outcome "AM2 oracle repair written; static validation pending"
```

### 4.3 Finish or stop

On successful static validation, run exactly these two operations:

```text
scripts/ai/aq-event pulse --agent codex-subagent-b2-m1a-am2-implementer --action validate --scope scripts/testing/test-workflow-shadow-migration.py --outcome "AM2 static validation passed; independent acceptance required"
python3 scripts/ai/lib/pending-update done b2-m1a-am2-20260719
```

On a mandatory stop before candidate editing, substitute exactly:

```text
scripts/ai/aq-event pulse --agent codex-subagent-b2-m1a-am2-implementer --action stop --scope scripts/testing/test-workflow-shadow-migration.py --outcome "AM2 stopped before candidate edit; see implementer handoff"
python3 scripts/ai/lib/pending-update failed b2-m1a-am2-20260719
```

On a mandatory stop after the candidate write, substitute exactly:

```text
scripts/ai/aq-event pulse --agent codex-subagent-b2-m1a-am2-implementer --action stop --scope scripts/testing/test-workflow-shadow-migration.py --outcome "AM2 stopped after bounded candidate edit; independent recovery required"
python3 scripts/ai/lib/pending-update partial-success b2-m1a-am2-20260719
```

Exactly one finish/stop branch may run. The canonical writers may perform their normal timestamp,
event-ID, append, projection, atomic replacement, and bounded-decay behavior. Their internal evidence
writes are terminal governance emissions and do not recursively require another pulse. They confer
no authority to change candidate scope or live system state.

## 5. Exact implementation and validation allowance

The implementer must implement all requirements in AM2 design section 1 without weakening an
existing assertion. The entire write/executable allowance after orientation is:

| Primitive | Exact permitted use |
|---|---|
| `apply_patch` | edit only `scripts/testing/test-workflow-shadow-migration.py` |
| `python3 scripts/testing/test-workflow-shadow-migration.py` | no arguments, no wrapper or environment override; once per implementation iteration |
| `python3 -c` static compile | exactly `import pathlib, py_compile; p=pathlib.Path('/tmp/b2-m1a-am2-test-workflow-shadow-migration.pyc'); py_compile.compile('scripts/testing/test-workflow-shadow-migration.py', cfile=str(p), doraise=True); p.unlink(missing_ok=True)` |
| `python3 -c` JSON parse | standard-library parse of exactly `config/workflow-shadow-db-privileges.json` and `config/validation-check-registry.json`, with no import of either migration or the oracle |
| sections 3 and 4 primitives | bounded orientation, governance evidence, before/after hashes, source review, path-limited status/diff, and whitespace evidence only |

The candidate must remain standard-library-only, deterministic, no-argument, and offline. Its final
truthful output remains:

```text
B2-M1A static oracle: PASS; authority=legacy_json_authoritative coverage=migration_artifacts_static_only
```

The implementer must record each operation and result. No repository `__pycache__`, `.pyc`, fixture,
snapshot, generated product output, or non-canonical evidence log may be created. Section 4's exact
event/projection evidence is the sole exception.

## 6. Prohibitions and mandatory stops

The implementer must stop immediately, make no further candidate edit, and report the exact condition
if any of the following occurs:

- an evidence/predecessor digest mismatch, frozen-row drift, need for an eighth candidate path, or
  need for any operation outside sections 3 through 5;
- `--integration`, `--dsn-file`, M1E token, alternate oracle argument, or environment-provided
  execution path;
- Alembic in any command/API/render mode, migration import/execution, SQL/DDL execution or render,
  database client/driver/DSN, PostgreSQL, DNS, socket, or network access;
- any subprocess/child-process launch other than the exact allowlisted orientation and static
  validation commands; candidate code may not import or invoke subprocess/process APIs;
- Nix evaluation/build/activation, service/runtime action, deployment, traffic, cutover, dashboard
  claim, broad QA, Phase-0, Tier-0, full test suite, cleanup, rollback, or M1E;
- repository cache/generated-product creation, direct or arbitrary edits to governance evidence,
  staging, commit, destructive Git, deletion, archive, or authority expansion; or
- a claim that static success proves branch resolution, PostgreSQL syntax, applied DDL, grants,
  rollback, database health, schema readiness, migration readiness, or operational adoption.

There is no fail-closed exception. A prohibited attempt consumes the single-use activation even if
it returns before a side effect. Orientation and canonical governance operations explicitly listed
in sections 3 and 4 are compliant and must not be misclassified as candidate scope or violations.

## 7. Required evidence and independent acceptance

The implementation handoff must include:

- activated authorization hash, implementer identity, and owner activation window;
- evidence that the AM2 authorization was checked against mandatory `AGENTS.md` and
  `.agent/WORKFLOW-CANON.md` prerequisites before editing;
- before/after hashes for all seven candidate paths, with change only in row 5;
- exact operation log partitioned into orientation, governance events/projections, candidate edit,
  and static validation;
- default oracle `PASS`, exact syntax-compile `PASS`, exact JSON-parse `PASS`, and whitespace `PASS`;
- explicit confirmation of no integration argument, Alembic, migration import/execution, database,
  DSN, driver, SQL/DDL, network, socket, non-allowlisted child process, Nix, broad runner, deployment,
  staging, commit, runtime action, cache/generated product file, arbitrary governance-path edit, or
  authority expansion;
- exact RESUME, PENDING/intent, post-write PULSE, and finish/stop HANDOFF evidence created only by the
  literal canonical writers in section 4; and
- a statement that legacy `workflow-sessions.json` remains the sole live authority.

After implementation, a different independent reviewer must receive a newly frozen seven-hash
subject under a separately prepared, independently reviewed, and owner-activated static-acceptance
authorization. The implementation activation does not authorize acceptance. Only independent
`PASS` allows the orchestrator to stage or commit the bounded candidate.

M1E, database connectivity, DDL render/execution, grants, runtime adoption, deployment, traffic,
cutover, cleanup, rollback, and every later B2 slice remain unauthorized.

## 8. Activation record

Current activation state: **NOT ACTIVATED**.

Before activation:

1. an independent reviewer must issue exact-byte `PASS` on AM2 design revision 2 SHA-256
   `9b50fa84889c3c04ac4e38b0aab844c3571f1c258ad6b99cbc7536d70c251ba9`;
2. an independent reviewer must explicitly confirm this authorization is consistent with mandatory
   `AGENTS.md` and `.agent/WORKFLOW-CANON.md` prerequisites and issue `PASS` on this exact
   authorization hash; and
3. the owner must name this exact authorization SHA-256,
   `codex-subagent-b2-m1a-am2-implementer`, an activation timestamp, and an expiry no more than 24
   hours later, confirming the one-file ceiling and all stop conditions remain unchanged.

`RECORD: PREPARED_ONLY. This document authorizes no action until independently reviewed and explicitly
activated by the owner. Candidate acceptance, M1E, database/Alembic/DDL activity, Nix/deployment,
runtime adoption, staging, commit, and later B2 slices remain unauthorized.`


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `auth-aqos-foundation-b2-m1a-am2-20260719`, event_id `811d26fe3b374c279e0172fa160fd5ed`, ts `2026-07-19T03:38:59Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
