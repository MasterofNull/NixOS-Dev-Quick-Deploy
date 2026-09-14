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
