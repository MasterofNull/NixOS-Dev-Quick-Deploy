# Foundation B2-M1A amendment 1 design packet

**Slice:** B2-M1A-AM1 — close static source-to-policy oracle coverage
**Status:** **PREPARED_ONLY — DESIGN NOT ACTIVATED**
**Prepared date:** 2026-07-19 UTC
**Prepared against Git commit:** `53740c44fe590ac98f019918b99bbfd467feccb7`
**Recovery finding:** `B2-M1A-RECOVERY-ACCEPTANCE.md` at SHA-256
`813ef2ad5eeaf69c94efddadadfb5e8ba196d642d8955496d62981b17e1e846a`

This packet designs one bounded repair to the rejected B2-M1A candidate. It grants no authority to
edit, execute, stage, commit, connect to a database, invoke Alembic, or begin M1E.

## 1. Objective and evidence-grounded boundary

The recovery review proved four related omissions in the static oracle:

1. the oracle lists the existing AIDB head source but never reads it or verifies its exact
   `branch_labels = ("aidb",)` declaration;
2. delivery and reader table privileges are closed, but their schema and function cells are not;
3. policy function, trigger, index, constraint, and foreign-key identities are not compared to the
   migration source; and
4. the migration's policy digest binds policy bytes but cannot replace the missing semantic
   source-to-policy comparisons.

Read-only inspection confirms that all required truth already exists in two unchanged inputs:

- `config/workflow-shadow-db-privileges.json` contains the closed object and privilege identities;
- `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` emits those named objects; and
- `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` declares the AIDB branch label.

Therefore the entire repair fits in one existing candidate file:

| Operation | Path | Purpose |
|---|---|---|
| MODIFY | `scripts/testing/test-workflow-shadow-migration.py` | read and compare the already-bound AIDB source, policy, and dormant B2 migration source |

No policy, migration, Nix, registry, shell, runtime, dashboard, or additional test file may change.
If implementation discovers that another file is needed, it must stop without editing that file and
return `SCOPE_EXPANSION_REQUIRED` for a new design and authorization.

## 2. Frozen seven-file predecessor subject

Every digest must match before the one-file edit. A mismatch is a hard stop.

| # | Path | Predecessor SHA-256 |
|---:|---|---|
| 1 | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

## 3. Exact repair contract

The amended oracle must remain deterministic, offline, standard-library-only, and default-mode only.
It must add all of the following assertions without weakening an existing assertion.

### 3.1 AIDB branch-label source assertion

- Read the first authorized path as UTF-8 text during `run_static()` or a pure helper called by it.
- Parse it with `ast.parse` and require exactly one assignment each for `revision`, `down_revision`,
  `branch_labels`, and `depends_on`.
- Require the literal values `revision == "20260125_01"`, `down_revision == "20260109_02"`,
  `branch_labels == ("aidb",)`, and `depends_on is None`.
- Reject computed, duplicate, missing, or extra branch labels. A mere substring search is insufficient.
- Do not import or execute the migration and do not write bytecode.

### 3.2 Closed delivery and reader privilege cells

Require exact equality, including absence of extra keys, for:

```text
delivery = {
  "schema": ["USAGE"],
  "tables": {
    "workflow_outbox_event": ["SELECT"],
    "workflow_delivery_control": ["SELECT", "UPDATE"]
  },
  "functions": {}
}
reader = {
  "schema": ["USAGE"],
  "tables": {
    "workflow_snapshot": ["SELECT"],
    "workflow_outbox_event": ["SELECT"],
    "workflow_delivery_control": ["SELECT"]
  },
  "functions": {}
}
```

These checks must fail for an added schema privilege, function privilege, object, action, or field.

### 3.3 Exact named-object source binding

Require exact policy identities and require each identity in the corresponding migration DDL form:

- functions: `apply_workflow_transition_v1`, `reject_workflow_outbox_mutation_v1`;
- trigger: `workflow_outbox_immutable_v1` bound to
  `workflow_outbox_event` and `reject_workflow_outbox_mutation_v1`;
- indexes: `workflow_outbox_event_workflow_revision_uq` on
  `workflow_outbox_event(workflow_id, revision)` and
  `workflow_delivery_control_next_attempt_idx` on
  `workflow_delivery_control(next_attempt_at)`;
- constraints: `workflow_snapshot_revision_ck`, `workflow_snapshot_digest_ck`,
  `workflow_snapshot_terminal_ck`, `workflow_outbox_event_revision_ck`,
  `workflow_outbox_event_digest_ck`, `workflow_outbox_event_size_ck`,
  `workflow_outbox_event_schema_ck`, `workflow_delivery_control_lease_ck`,
  `workflow_delivery_control_attempt_ck`, `workflow_delivery_control_disposition_ck`,
  `workflow_delivery_control_error_ck`, `workflow_outbox_snapshot_fk`, and
  `workflow_delivery_outbox_fk`; and
- foreign-key map exactly:
  `workflow_outbox_snapshot_fk: workflow_outbox_event.workflow_id -> workflow_snapshot.workflow_id`
  and `workflow_delivery_outbox_fk: workflow_delivery_control.event_id ->
  workflow_outbox_event.event_id`.

Comparison must bind names to their object/table/column relationship, not only count or search for an
identity somewhere in the source. A small pure normalizer over the fixed migration source is allowed;
SQL execution, Alembic import, migration import, database parsing, or a new dependency is not.

The oracle must also keep the exact policy digest assertion. Semantic binding supplements rather
than replaces byte binding.

## 4. Validation and mutation tests

The amendment must demonstrate:

1. the default no-argument oracle passes;
2. the oracle source parses through `ast.parse` without import or bytecode;
3. read-only in-memory mutation vectors fail when the AIDB label is missing/substituted/duplicated;
4. mutation vectors fail for added delivery/reader schema or function privileges;
5. mutation vectors fail for missing, substituted, or wrongly bound function, trigger, index,
   constraint, and foreign-key identities; and
6. all six unchanged candidate paths retain their predecessor hashes.

Mutation vectors may operate only on in-memory strings or dictionaries. They must not write fixtures,
generate repository files, import either migration, invoke the integration entry point, or launch a
child process. If the one-file oracle cannot host these vectors without weakening its offline
boundary, implementation must stop rather than add a test path.

## 5. Absolute exclusions and truth boundary

This amendment permits no `--integration`, `--dsn-file`, M1E token, Alembic command/API, offline SQL
render, driver, client, DSN read, DNS, socket, network, subprocess, PostgreSQL access, DDL execution,
Nix evaluation/build/activation, service action, deployment, traffic, cutover, runtime hook,
dashboard claim, broad QA runner, Phase-0 runner, Tier-0 runner, cleanup, or rollback. Neither
migration may be imported or executed. No bytecode/cache may be generated.

Legacy `workflow-sessions.json` remains the sole live authority. A passing amended oracle proves only
static artifact consistency; it does not prove Alembic branch resolution, PostgreSQL syntax,
migration application, grants, rollback, database health, schema readiness, or M1E behavior.

## 6. Gates

1. An independent architecture/security/SRE reviewer must issue `PASS` on this exact design.
2. A single-use implementation authorization must bind this design hash, the complete recovery
   lineage, and the exact predecessor hashes.
3. A different independent reviewer must issue `PASS` on that exact authorization.
4. The owner must explicitly activate the authorization's exact hash, name the implementer, and set
   an expiry no more than 24 hours after activation.
5. A different independent acceptance reviewer must bind the amended seven-file hashes and issue
   `PASS` before the orchestrator may stage or commit the candidate.

`RECORD: PREPARED_ONLY. This design authorizes no implementation or acceptance action.`
