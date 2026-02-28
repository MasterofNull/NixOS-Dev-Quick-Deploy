#!/usr/bin/env bash
# scripts/import-ai-behavior-snapshot.sh
#
# Imports AI behavior snapshot files back into AIDB on a fresh deploy.
# This script is fully idempotent — safe to run after every deploy.
#
# What it imports:
#   ai-stack/snapshots/query-gaps.jsonl  → query_gaps table (ON CONFLICT DO NOTHING)
#   ai-stack/snapshots/imported-documents-meta.jsonl  → skipped (re-imported by
#       import-agent-instructions.sh which has full content and upsert semantics)
#
# Environment (all optional — overridable via env):
#   POSTGRES_HOST        DB host (default: localhost)
#   POSTGRES_PORT        DB port (default: 5432)
#   POSTGRES_DB          DB name (default: aidb)
#   POSTGRES_USER        DB user (default: aidb)
#   POSTGRES_PASSWORD_FILE  Path to password file (default: /run/secrets/postgres_password)
#
# Usage:
#   bash scripts/import-ai-behavior-snapshot.sh
#   POSTGRES_HOST=other-host bash scripts/import-ai-behavior-snapshot.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_DIR="${REPO_ROOT}/ai-stack/snapshots"
GAPS_FILE="${SNAPSHOT_DIR}/query-gaps.jsonl"

PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_DB="${POSTGRES_DB:-aidb}"
PG_USER="${POSTGRES_USER:-aidb}"
PG_PASS_FILE="${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}"

# --- Read postgres password ---
if [[ ! -r "$PG_PASS_FILE" ]]; then
    printf 'import-ai-behavior-snapshot: cannot read %s\n' "$PG_PASS_FILE" >&2
    exit 1
fi
export PGPASSWORD
PGPASSWORD="$(tr -d '[:space:]' < "$PG_PASS_FILE")"

# ---------------------------------------------------------------------------
# AIDB creates the query_gaps table on startup — do not attempt to recreate it
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Import query_gaps.jsonl
# ---------------------------------------------------------------------------
INSERTED=0
SKIPPED=0

if [[ ! -f "$GAPS_FILE" ]]; then
    printf 'import-ai-behavior-snapshot: %s not found — skipping query_gaps import\n' "$GAPS_FILE"
else
    # Check for placeholder written by export script when table was missing
    first_line="$(head -1 "$GAPS_FILE")"
    if printf '%s' "$first_line" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('note') else 1)" 2>/dev/null; then
        printf 'import-ai-behavior-snapshot: query-gaps.jsonl contains placeholder — nothing to import\n'
    else
        # Stream each JSONL line through python3 → psql
        # python3 batches into a single multi-value INSERT for efficiency
        python3 - "$GAPS_FILE" "$PG_HOST" "$PG_PORT" "$PG_DB" "$PG_USER" <<'PYEOF'
import json
import os
import subprocess
import sys

gaps_file = sys.argv[1]
pg_host   = sys.argv[2]
pg_port   = sys.argv[3]
pg_db     = sys.argv[4]
pg_user   = sys.argv[5]

rows = []
with open(gaps_file) as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        query_hash  = rec.get("query_hash", "")
        query_text  = rec.get("query_text", "")
        score       = rec.get("score")
        collection  = rec.get("collection", "")
        created_at  = rec.get("created_at", "")
        if not query_hash:
            continue
        rows.append((query_hash, query_text, score, collection, created_at))

if not rows:
    print("import-ai-behavior-snapshot: query-gaps.jsonl has no valid rows")
    sys.exit(0)

# Build one SQL statement for the entire batch
def esc(s):
    """Escape a string value for SQL literal."""
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"

value_clauses = []
for query_hash, query_text, score, collection, created_at in rows:
    score_sql = str(score) if score is not None else "NULL"
    ts_sql    = esc(created_at) if created_at else "NOW()"
    value_clauses.append(
        "({}, {}, {}, {}, {})".format(
            esc(query_hash),
            esc(query_text),
            score_sql,
            esc(collection),
            ts_sql,
        )
    )

sql = (
    "INSERT INTO query_gaps (query_hash, query_text, score, collection, created_at)\n"
    "VALUES\n  " + ",\n  ".join(value_clauses) + "\n"
    "ON CONFLICT (query_hash) DO NOTHING;\n"
    "SELECT changes_inserted, changes_skipped FROM\n"
    "  (SELECT COUNT(*) AS changes_inserted FROM query_gaps) x,\n"
    "  (SELECT 0 AS changes_skipped) y;\n"
)

# We can't easily get affected-row counts from ON CONFLICT DO NOTHING via psql
# stdout, so we record totals before/after instead.
count_sql = "SELECT COUNT(*) FROM query_gaps;"

env = os.environ.copy()
result_before = subprocess.run(
    ["psql", "-h", pg_host, "-p", pg_port, "-U", pg_user, "-d", pg_db,
     "--no-psqlrc", "-t", "-A", "-c", count_sql],
    capture_output=True, text=True, env=env
)
before = int(result_before.stdout.strip()) if result_before.returncode == 0 else 0

# Idempotent: skip if table already has data (fresh-deploy seeding only)
if before > 0:
    print("import: query_gaps already has {} rows — skipping (idempotent)".format(before))
    sys.exit(0)

# Run the INSERT (no ON CONFLICT — query_gaps uses SERIAL id, not query_hash PK)
subprocess.run(
    ["psql", "-h", pg_host, "-p", pg_port, "-U", pg_user, "-d", pg_db,
     "--no-psqlrc", "-q", "-c",
     "INSERT INTO query_gaps (query_hash, query_text, score, collection)\n"
     "VALUES\n  " + ",\n  ".join(
         "({}, {}, {}, {})".format(
             esc(qh), esc(qt), str(sc) if sc is not None else "NULL", esc(co)
         )
         for qh, qt, sc, co, _ in rows
     ) + ";"],
    check=True, env=env
)

result_after = subprocess.run(
    ["psql", "-h", pg_host, "-p", pg_port, "-U", pg_user, "-d", pg_db,
     "--no-psqlrc", "-t", "-A", "-c", count_sql],
    capture_output=True, text=True, env=env
)
after = int(result_after.stdout.strip()) if result_after.returncode == 0 else 0

total   = len(rows)
inserted = after - before
skipped  = total - inserted

print("import: {} query_gaps inserted, {} skipped".format(inserted, skipped))
PYEOF
        # Capture inserted/skipped from python output
        INSERTED="$(python3 - "$GAPS_FILE" "$PG_HOST" "$PG_PORT" "$PG_DB" "$PG_USER" <<'PYEOF2' 2>/dev/null || printf '0'
import json, sys
rows = sum(1 for line in open(sys.argv[1]) if line.strip() and not line.strip().startswith('{') or
           (line.strip().startswith('{') and not json.loads(line.strip()).get('note')))
print(rows)
PYEOF2
)"
        # Reset to zero if python3 block already printed; the embedded python above
        # already printed the summary line. We do not reprint.
        INSERTED=0
        SKIPPED=0
    fi
fi

# ---------------------------------------------------------------------------
# imported-documents-meta.jsonl — intentionally skipped
# ---------------------------------------------------------------------------
printf 'import-ai-behavior-snapshot: imported-documents-meta.jsonl skipped (use import-agent-instructions.sh)\n'

# ---------------------------------------------------------------------------
# Final summary (only when we did not delegate to python)
# ---------------------------------------------------------------------------
if [[ "$INSERTED" -eq 0 && "$SKIPPED" -eq 0 ]]; then
    : # summary already printed by embedded python
else
    printf 'import: %s query_gaps inserted, %s skipped\n' "$INSERTED" "$SKIPPED"
fi
