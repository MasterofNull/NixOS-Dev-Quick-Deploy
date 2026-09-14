# Schema SSOT — read this before touching any *.sql in this repo

**This Alembic tree (`ai-stack/migrations/versions/*.py`) is the ONE authoritative live database schema.**
The deployed PostgreSQL is provisioned by `alembic -c ai-stack/migrations/alembic.ini upgrade aidb@head`,
wired at deploy time in `nix/modules/services/mcp-servers.nix`. Change the live schema ONLY by adding an
Alembic revision here.

Other `*.sql` / `schema/` locations in the repo are NOT the live schema:
- `ai-stack/postgres/migrations/` + `docs/sql/aidb-timeseries-schema.sql` — a SECONDARY manual path applied by
  `scripts/data/apply-autonomous-improvement-migration.sh` / `bootstrap-aidb-data.sh`; being reconciled into
  Alembic (see `.agents/plans/agentic-db-hygiene/DESIGN.md`, slice db-3).
- `ai-stack/postgres/init-schema.sql`, `ai-stack/aidb/schema/`, `ai-stack/database/postgres/`, `ai-stack/sql/`,
  `ai-stack/workflows/schema/` — legacy/superseded copies with NO live consumers; pending archival (db-2).
  Do not treat their tables/fields as current — they are the "blank/old/unused" tables you may have seen.

Full picture + cleanup plan: `.agents/plans/agentic-db-hygiene/DESIGN.md`.
