# Agentic-Database Hygiene + Integration Audit (Phase-1 Databases)

**Owner priority (2026-09-14 pivot):** Phase-1 = Core Engine, Identity, Leases, **Databases**. Owner
noticed the repo DB "has many tables and fields that seem blank/old/not used" and asked whether it is the
template for the deployed DB. This plan captures the investigation answer + the bounded cleanup.

## Finding 1 — the repo holds the schema TEMPLATE; live data lives in the deployment
The deployed PostgreSQL is provisioned SOLELY by **Alembic** — `ai-stack/migrations/versions/*.py`, applied
at deploy time by `alembic -c ai-stack/migrations/alembic.ini upgrade aidb@head`
(`nix/modules/services/mcp-servers.nix:950`). That is the ONE authoritative live schema. Blank tables in the
repo are normal: the repo defines STRUCTURE, the running system holds the DATA (verified heavily populated —
Qdrant interaction-history ~41K points, knowledge ~16K, etc.). Confirmed consumer counts (non-sql refs):
`alembic` = 35, `ai-stack/migrations` = 8; everything below is far less or dead.

## Finding 2 — schema is FRAGMENTED across ~9 locations; most are unwired ("old/unused")
Enumerated schema/migration locations and their real code consumers (grep of nix/ scripts/ ai-stack/
dashboard/, excluding *.sql and archive/worktrees):

| Location | Live consumer? | Disposition |
|---|---|---|
| `ai-stack/migrations/versions/` (alembic) | YES — the deploy path (mcp-servers.nix:950) | **SSOT — keep** |
| `ai-stack/postgres/migrations/` (5 sql) | YES — `scripts/data/apply-autonomous-improvement-migration.sh` applies `006_autonomous_improvement.sql` | LIVE but OUTSIDE alembic → **reconcile into alembic** |
| `docs/sql/aidb-timeseries-schema.sql` | YES — `scripts/data/bootstrap-aidb-data.sh` | LIVE bootstrap outside alembic → **reconcile / document** |
| `ai-stack/postgres/init-schema.sql` (15 CREATE TABLEs) | **NO (0 consumers)** — not in code, nix, or live docker | **candidate-dead → archive after per-file proof** |
| `ai-stack/aidb/schema/` (2 sql + migrations) | **NO (0)** | candidate-dead → archive |
| `ai-stack/database/postgres/` (+migrations) | **NO (0)** | candidate-dead → archive |
| `ai-stack/sql/` (4 sql) | **NO (0)** | candidate-dead → archive |
| `ai-stack/workflows/schema/` | **NO (0)** | candidate-dead → archive |

The blank/old tables the owner saw are almost certainly these zero-consumer legacy copies — NOT the live
schema. (All docker-compose references to these live only under `archive/` and `.claude/worktrees/`.)

## Finding 3 — committed empty runtime DB (cruft)
`ai-stack/autoresearch/experiments.sqlite` is TRACKED but EMPTY (tables `experiments`, `task_completions`,
0 rows). It is a RUNTIME database: `ai-stack/autoresearch/autoresearch.py` writes it, `ai-stack/
autonomous-improvement/trend_database.py` reads it. Runtime DBs must be gitignored + generated at runtime —
its sibling `ai-stack/eval/results/scores.sqlite` already is (`.gitignore:113`). Committing it is inconsistent.

## Finding 4 — agentic-memory ALIVE but UNEVENLY integrated (prior assessment, issues-backlog)
Qdrant/redis/postgres/AIDB/coordinator all healthy + heavily used, but: episodic memory tier thin (7 pts vs
semantic 170); live agent-ctx write recency stale (newest 2026-08-28); 15 ephemeral agent-ctx-* collections
not GC'd; `redis-mcp.service` is the real server while `redis`/`redis-ai` units read inactive (misleading).

## Slices (each: bounded, non-author review, tier0 gate, trunk envelope)
- **db-1 (SAFE, this commit):** untrack `experiments.sqlite` + gitignore it (match scores.sqlite). Add this
  plan + a one-line SCHEMA-SSOT pointer so alembic-is-authoritative is never ambiguous again.
- **db-2 (reviewed archival):** for EACH zero-consumer location, re-prove non-use (grep runtime/bootstrap/
  docker/human-runbook consumers, incl. variable-constructed paths) then ARCHIVE (Rule 12, never delete) under
  `.agent/archive/<date>-legacy-schema/`. `ai-stack/postgres/` is MIXED — archive only `init-schema.sql`,
  keep `migrations/`. Do NOT archive anything whose non-use is not proven.
- **db-3 (reconcile secondary SQL):** fold `006_autonomous_improvement.sql` + `aidb-timeseries-schema.sql`
  into the alembic lineage (or document them as an explicit, gated supplementary path) so there is ONE
  provisioning story. Verify against a fresh-install DB (ties into installer s1c/s1d re-seed).
- **db-4 (agentic-memory integration audit):** per-tier memory-health surface — fix episodic write path,
  verify agent-ctx recency (aq-agent-loop), GC ephemeral collections, rename/clarify the redis unit. Make
  each memory tier observable on the dashboard (blank `--` = bug).

## Constraints
NixOS declarative-only; never delete (archive, Rule 12); prove non-use before archiving any schema; do not
hand-edit any pinned hash or fake a green (anti-gaming, Rule 19); ports/paths from env.

## db-2 investigation results (2026-09-14) — per-file dead-vs-live map
Filename-ref=0 does NOT alone prove a schema file dead (its TABLES may be used); verified table-level too.
- **ARCHIVED (proven dead, this slice → `.agent/archive/20260914-legacy-schema/`):** all of `ai-stack/sql/`
  (update_package_versions_jan2026.sql, comprehensive_update_jan2026.sql = one-off Jan-2026 DML data updates;
  package_versions_schema.sql, add_ralph_repos_metadata.sql = DDL for tables `package_versions` /
  `ralph_implementations` that ZERO live code references). Nothing loads these at runtime; reversible (Rule 12).
- **db-2b FOLLOW-UP (referenced/entangled — do NOT archive without subsystem verification):**
  - `ai-stack/aidb/schema/*.sql` (temporal-facts-v2, interaction-history-v1, migrations/001_temporal_facts) —
    listed in `config/ai-harness-slice-registry.json` + docs/architecture/memory-system-design.md. Verify the
    registered slice is retired before touching.
  - `ai-stack/database/postgres/migrations/` — an ORPHANED second alembic tree (env.py + 9 versions:
    tool_registry, imported_documents, open_skills, pgvector_embeddings, codemachine_workflows, status_flags,
    system_registry) with NO alembic.ini wiring it. But `V20__world_model_query_patterns.sql` (sibling) is
    referenced by live `ai-stack/world-model/pattern_index.py`. Determine how these tables get created on a
    real deploy (they're not in the wired alembic) — either fold into the SSOT alembic (db-3) or archive if
    truly abandoned. Needs world-model + tool-registry subsystem check.
  - `ai-stack/postgres/init-schema.sql` (15-table "centralized" predecessor init, 0 refs) — needs a
    table-by-table overlap check against the live alembic head before archiving (confirm every table it
    defines is either in alembic or genuinely unused; then archive as superseded).
- **NOT DB schema (out of db-2 scope, leave):** `ai-stack/database/postgres/schemas/*.json` (workflow output
  schemas: draft-plan/context-scan/web-brief/final-aggregation), `ai-stack/workflows/schema/workflow-v1.yaml`.

## db-4 F2 LANDED (2026-09-14) — ephemeral-collection GC
Declarative weekly GC for stale `agent-ctx-*` Qdrant scratch collections: `scripts/ai/qdrant-scratch-gc.py`
+ `mySystem.deployment.qdrantScratchGc` {enable (default true), retentionDays (default 14)} in options.nix
+ a systemd oneshot service + weekly timer (OnCalendar Sun 09:00) in ai-stack.nix. Safety is defense-in-depth
(only `agent-ctx-` prefix, prefix re-asserted before every delete, undeterminable-age fail-safe skip,
per-collection try/except). Dry-run verified against live Qdrant: 18 agent-ctx-* candidates, 0
protected/operational collections touched. Observability: journal logs + the F1 dashboard ephemeral-count.
Activation: owner nixos-rebuild turns the timer ON; the first sweep prunes the 17 age-determinable stale
collections (>17d old); the 18th (agent-ctx-test-task-large-live-rfgate-74775, unparseable name = undeterminable
age) is skipped-unknown by the fail-safe and never deleted.
The suspend/resume contract policy (config/suspend-resume-workloads.json) was updated to acknowledge
qdrant-scratch-gc as a periodic timer-oneshot with no resumable in-flight state.
