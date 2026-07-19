# Foundation B2-M1A amendment 2 static acceptance

**Verdict artifact for:** `auth-aqos-foundation-b2-m1a-am2-acceptance-20260719`
**Reviewer identity:** `claude-subagent-b2-m1a-am2-acceptance-reviewer`
**Reviewer model:** Claude Fable 5 (`claude-fable-5`), flagship tier, fresh session — did not implement
the candidate and did not produce the orchestrator spot-review
**Review date:** 2026-07-19 UTC (within activation window 2026-07-19T05:00:00Z → 2026-07-20T05:00:00Z)
**Authorization verified:** `.agents/plans/aqos-foundation-b2/B2-M1A-AM2-STATIC-ACCEPTANCE-AUTHORIZATION.md`
recomputed SHA-256 `a8961842282a8d330f9804eebe1a55c2ac1979593485629487273be84798d251` — exact match.
Owner activation confirmed in `.agent/collaboration/PULSE.log`: `[owner] [standing-authorization]`
(2026-07-18T21:33:26-0700) and `[owner] [acceptance-activated]` (2026-07-18T21:33:33-0700) naming this
exact document hash, this reviewer identity, and the 24-hour window.

## 1. Recomputed seven-hash subject (criterion 1)

All hashes recomputed fresh by this reviewer via `sha256sum`:

| # | Path | Recomputed SHA-256 | Match |
|---:|---|---|---|
| 1 | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` | FROZEN, matches |
| 2 | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` | FROZEN, matches |
| 3 | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` | FROZEN, matches |
| 4 | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` | FROZEN, matches |
| 5 | `scripts/testing/test-workflow-shadow-migration.py` | `712ed6b0dd30d2ced10a0ebc2eded0721fc85a7d301b9b6d640e323389080bcd` | CANDIDATE, matches required |
| 6 | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` | FROZEN, matches |
| 7 | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` | FROZEN, matches |

Rows 1–4 and 6–7 equal their predecessors byte-identically. Row 5 differs from predecessor
`208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` and equals the required candidate
hash exactly. **Criterion 1: PASS.**

## 2. Lineage verification (authorization section 2)

All recomputed by this reviewer:

| Document | Recomputed SHA-256 | Match |
|---|---|---|
| `B2-M1A-AM2-DESIGN-PACKET.md` | `9b50fa84889c3c04ac4e38b0aab844c3571f1c258ad6b99cbc7536d70c251ba9` | matches |
| `B2-M1A-AM2-IMPLEMENTATION-AUTHORIZATION.md` | `82e9edc61e23239a803691b3769c2e9cb2b22c9ee02915269c5b3e8026b43c09` | matches |
| `B2-M1A-AM2-AUTHORIZATION-REVIEW.md` | `b5c8afde8746f85034d76249e13151eabe8b53a6ca6280adf0082e854c5d542e` | matches |
| `B2-M1A-AM2-AUTHORIZATION-REVIEW-R2.md` | `0f1610d94d0837f1e3b67ac4f2488f5f275000809f53eb4eafcbce4a8cbba467` | matches |
| `B2-M1A-AM1-DESIGN-PACKET.md` | `7c799909421c73aa276a45d266d9abcd52f45ff58feebde2f2733672923322c3` | matches |
| `B2-M1A-AM1-WORKFLOW-CONFLICT-INCIDENT.md` | `854733d2b7567336576d16e5ba092da3a034d764f8d9830d2fe4ee12644b0edc` | matches |
| `AGENTS.md` | `1e1019757d035f9934839c6d71a7c8981c70ca29b7dec436b47a95aa686b29b2` | matches |
| `.agent/WORKFLOW-CANON.md` (current) | `3ddc1f4b5d649d575797def0c87b1542e750aa4128d42627564c9d2f1eeafa72` | matches |

WORKFLOW-CANON dual-hash note verified: the implementation-time version
(`8775c67fa415a6f3a9be6d66597aa911c8017f817633cbb9cb0684450fa51e4a`) exists at Git commit
`b8a805366d72b6280bf16c866e7a5ada43273b59`; `git diff b8a80536 -- .agent/WORKFLOW-CANON.md` shows the
delta is confined to exactly one added block — the "Cheapest-eligible implementer" Rule-17 canonical
addition (12 inserted lines after the outer-loop preamble). No other line changed. **Lineage: PASS.**

## 3. Per-criterion evidence

### Criterion 2 — AM1 design section 3 fully implemented, no assertion weakened: PASS

Verified by full read of the candidate source (564 lines):

- **Literal AST AIDB branch binding** (`check_aidb_branch_source`, lines 115–153): parses the AIDB
  migration with `ast.parse`; collects `ast.Assign` targets for `revision`/`down_revision`/
  `branch_labels`/`depends_on`; requires exactly one assignment each (`len(values) == 1` — missing,
  duplicate, and extra assignments all fail); requires `ast.Constant` literals
  `"20260125_01"`/`"20260109_02"`/`None` and an `ast.Tuple` of length 1 whose sole element is the
  constant `"aidb"` — computed values and substituted/extra labels fail; no import, execution, or
  bytecode. Substring search is not used.
- **Closed privilege cells** (`check_policy`, lines 265–287): exact dict equality (`==`) for
  `grants["writer"]` (tables `{}`, single EXECUTE function), `grants["delivery"]` (functions `{}`,
  exact two-table map), `grants["reader"]` (functions `{}`, exact three-table map), plus
  `set(grants) == {"public","writer","delivery","reader"}` and `grants["public"] == []`. Any added
  schema privilege, function privilege, object, action, or field fails equality.
- **Exact named-object relationship binding** (`check_named_object_bindings`, lines 322–400): each
  function bound via its `CREATE FUNCTION {SCHEMA}.<name>(` form; the trigger bound by a three-line
  exact string tying `workflow_outbox_immutable_v1` to `workflow_outbox_event` AND
  `reject_workflow_outbox_mutation_v1()`; both indexes bound name→table→column-list; every CHECK
  constraint bound inside its owning table's `bind_slice` block; both foreign keys bound inside the
  owning table block with exact owning column and `REFERENCES {SCHEMA}.<table>(<column>)` target;
  coverage equality `set(constraints) == CHECK-owners ∪ FK-names`. This is relationship binding, not
  presence-anywhere.
- **Policy digest retention** (lines 504–505): recomputes SHA-256 over the policy bytes and requires
  the literal `PRIVILEGE_POLICY_SHA256 = "<digest>"` in the migration source. Byte binding retained;
  semantic binding supplements it.
- **Fail-closed negative mutations in the default path** (`check_mutation_vectors`, lines 411–475,
  invoked unconditionally from `run_static`): ten pure in-memory vectors — AIDB label
  missing/substituted/duplicated (AM1 §4.3); delivery schema privilege added and reader function
  privilege added via `copy.deepcopy` (AM1 §4.4); function renamed, trigger rebound to wrong table,
  index rebound to wrong column, CHECK constraint renamed, FK retargeted to wrong table (AM1 §4.5).
  Each is proven to fail closed via `expect_rejection`, which raises if the mutation does NOT fail.
  Vectors operate only on in-memory strings/dicts; no fixture, file write, migration import, or child
  process.
- **No prior assertion weakened**: the predecessor was never committed (candidate is a new untracked
  file), so byte-diff against `208a9bf2...` is not possible; verified structurally instead. The
  predecessor's assertion surface recorded in `B2-M1A-RECOVERY-ACCEPTANCE.md` (migration-surface
  invariants, policy checks limited to delivery/reader table maps, callers/registry checks, M1E
  fail-closed refusal, digest binding, prohibited-import self-check) is present in the candidate in
  equal or strictly stronger form — the recovery acceptance's four documented defects (no exact-cell
  equality, membership-only object lists, no source binding, digest-only closure) are exactly what
  the candidate adds. `check_python_surface`, `check_callers_and_registry`, `integration_refusal`
  (exit 77, `M1E_NOT_AUTHORIZED` before any DSN read on every gate branch), and the 16-item
  `M1E_REQUIRED_EVIDENCE` plan are all intact.

### Criterion 3 — four static validations re-run fresh: PASS

| Validation | Command run by this reviewer | Result |
|---|---|---|
| default oracle | `python3 scripts/testing/test-workflow-shadow-migration.py` | exit 0; exact literal line `B2-M1A static oracle: PASS; authority=legacy_json_authoritative coverage=migration_artifacts_static_only` |
| static compile | exact section-5 command: `python3 -c "import pathlib, py_compile; p=pathlib.Path('/tmp/b2-m1a-am2-test-workflow-shadow-migration.pyc'); py_compile.compile('scripts/testing/test-workflow-shadow-migration.py', cfile=str(p), doraise=True); p.unlink(missing_ok=True)"` | exit 0; cache file unlinked |
| JSON parse | stdlib `json.load` of `config/workflow-shadow-db-privileges.json` and `config/validation-check-registry.json` | both parse; exit 0 |
| whitespace | `git diff --check -- scripts/testing/test-workflow-shadow-migration.py` | clean; exit 0 |

### Criterion 4 — standard-library-only, deterministic, offline: PASS

Candidate imports (verified against full source): `argparse`, `ast`, `copy`, `hashlib`, `json`, `re`,
`stat`, `sys`, `time`, `pathlib` — all standard library. No import or invocation of
subprocess/socket/os/db-driver/Alembic APIs anywhere in the candidate. The oracle's own
prohibited-import self-check (lines 509–519, denying `socket`, `subprocess`, `psycopg`, `psycopg2`,
`sqlalchemy`, `alembic`, `os`) is intact and passed during the fresh oracle run. Default path takes
no arguments; any `--dsn-file`/`--evidence-token` without `--integration` fails closed
(`M1E_NOT_AUTHORIZED`, exit 77). Minor non-blocking observation: `import sys` (line 17) appears
unused — cosmetic only, standard library, violates no criterion.

### Criterion 5 — governance trail via canonical writers only: PASS

- Phase-start resume event: `RESUME.json` `agent_snapshots["codex-subagent-b2-m1a-am2-implementer"]`
  (objective "Implement B2-M1A-AM2 one-file static oracle repair", phase "B2-M1A-AM2
  implementation", updated ~2026-07-19T03:50:43Z, immediately before dispatch).
- PENDING intent: `pending-update list` shows `b2-m1a-am2-20260719 [done]
  agent=codex-subagent-b2-m1a-am2-implementer`.
- Candidate-write pulse: PULSE.log line 283 (2026-07-18T20:51:52-0700, action `write`).
- Validate pulse: PULSE.log line 284 (2026-07-18T20:52:30-0700, action `validate`, "independent
  acceptance required").
- HANDOFF lines: dispatch (`2026-07-19T03:50:47Z id=b2-m1a-am2-20260719`) and done
  (`2026-07-19T03:52:30Z`), canonical event-projection format.

### Criterion 6 — no live-authority claims: PASS

The candidate's only success claim is the exact truth-bounded line
(`authority=legacy_json_authoritative coverage=migration_artifacts_static_only`). No
branch-resolution, PostgreSQL, applied-DDL, grants, rollback, schema-readiness, or
operational-adoption claim appears in the candidate or in the governance evidence (pulses state
"static validation passed; independent acceptance required"). The integration entry point remains a
pure fail-closed refusal with no database driver. Legacy `workflow-sessions.json` remains the sole
live authority.

## 4. Disclosed-deviation adjudication

1. **Implementer identity substitution — ADEQUATELY COVERED.** Codex quota exhaustion is directly
   evidenced in `.agents/delegation/outputs/codex-20260718-204057-i0hlfyxxxxxx.log` ("You've hit
   your usage limit … try again at Jul 25th, 2026" after SessionStart — the session never executed
   the slice). The owner's override is recorded directly (not via an agent) in PULSE.log at
   2026-07-18T20:52:57-0700, names the exact implementation-authorization hash `82e9edc6...`, and
   preserves all other terms. Governance events carry the literal
   `codex-subagent-b2-m1a-am2-implementer` string per the authorization's exact-argument
   requirement; the true Claude Sonnet identity is disclosed in the override entry and the
   implementer's evidence. The durable record is internally consistent and complete.
2. **Retroactive override timing — ADEQUATELY COVERED.** The override (20:52:57) postdates the
   candidate-write pulse (20:51:52) and validate pulse (20:52:30) by about one minute. The owner's
   text explicitly acknowledges the retroactivity and states it covers the in-progress edit. The
   identical substitution basis was recorded by the owner for the sibling QPPR slice at 20:49:38 —
   before this candidate's write pulse — showing the owner's substitution intent predated the write
   even though the B2-specific entry landed after. Decisively, the candidate bytes are hash-frozen
   (`712ed6b0...` verified by this reviewer) and independent of the timing; nothing about the
   sequence altered candidate content, scope, or ceiling. Adequate for acceptance; noted as a
   process pattern to avoid repeating.
3. **Advisory spot-review — NOT ANCHORED.** This review re-derived every check independently: all
   fifteen hashes recomputed, all four validations re-run, full candidate code read, WORKFLOW-CANON
   delta re-diffed from Git history, governance trail checked at source. The spot-review pulse
   correctly labels itself "NOT formally accepted". No finding here relies on it. (Independent
   concurrence: its noted vector-count discrepancy is confirmed — the code contains ten negative
   mutation vectors, not nine as the implementer reported; inaccurate count in prose only, not a
   candidate defect.)

## 5. Verdict

All seven subject hashes match; lineage verified including the confined Rule-17 WORKFLOW-CANON
delta; all six acceptance criteria pass on independently re-derived evidence; all three disclosed
deviations are adequately covered by the durable record.

Scope of this verdict: it authorizes only the orchestrator to run
`scripts/governance/tier0-validation-gate.sh --pre-commit`, stage, and commit the exact accepted
seven-hash subject. M1E, database/Alembic/DDL activity, Nix/deployment, runtime adoption, and later
B2 slices remain unauthorized.

VERDICT: PASS
