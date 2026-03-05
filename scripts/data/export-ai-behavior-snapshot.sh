#!/usr/bin/env bash
# scripts/data/export-ai-behavior-snapshot.sh
#
# Exports AI behavior data from the live AIDB PostgreSQL database to
# git-tracked JSONL/JSON files under ai-stack/snapshots/.
#
# Exports:
#   ai-stack/snapshots/query-gaps.jsonl           — one row per query_gaps record
#   ai-stack/snapshots/imported-documents-meta.jsonl — metadata (no content) from imported_documents
#   ai-stack/snapshots/hint-adoption-summary.json — aggregated hint adoption counts
#
# Environment (all optional — overridable via env):
#   AIDB_URL             Base URL for AIDB (default: http://127.0.0.1:8002)
#   POSTGRES_HOST        DB host (default: localhost)
#   POSTGRES_PORT        DB port (default: 5432)
#   POSTGRES_DB          DB name (default: aidb)
#   POSTGRES_USER        DB user (default: aidb)
#   POSTGRES_PASSWORD_FILE  Path to password file (default: /run/secrets/postgres_password)
#   HINT_AUDIT_LOG_PATH  Path to hint-audit.jsonl
#
# Usage:
#   bash scripts/data/export-ai-behavior-snapshot.sh
#   POSTGRES_HOST=other-host bash scripts/data/export-ai-behavior-snapshot.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_DIR="${REPO_ROOT}/ai-stack/snapshots"

# --- Service coordinates (never hardcoded) ---
AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_DB="${POSTGRES_DB:-aidb}"
PG_USER="${POSTGRES_USER:-aidb}"
PG_PASS_FILE="${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}"
HINT_AUDIT_LOG="${HINT_AUDIT_LOG_PATH:-/var/log/nixos-ai-stack/hint-audit.jsonl}"

# --- Read postgres password ---
if [[ ! -r "$PG_PASS_FILE" ]]; then
    printf 'export-ai-behavior-snapshot: cannot read %s\n' "$PG_PASS_FILE" >&2
    exit 1
fi
export PGPASSWORD
PGPASSWORD="$(tr -d '[:space:]' < "$PG_PASS_FILE")"

mkdir -p "$SNAPSHOT_DIR"

# ---------------------------------------------------------------------------
# Helper: run a psql query and emit one JSON object per row as JSONL
# Args: output_file  sql_query
# ---------------------------------------------------------------------------
_export_jsonl() {
    local out_file="$1"
    local sql="$2"

    # psql JSON mode: wrap each row in a JSON object via row_to_json
    local wrapped_sql
    wrapped_sql="COPY (SELECT row_to_json(t) FROM (${sql}) t) TO STDOUT;"

    psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
        --no-psqlrc -t -A \
        -c "$wrapped_sql" > "$out_file" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Helper: check whether a table exists in the DB
# ---------------------------------------------------------------------------
_table_exists() {
    local tbl="$1"
    psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
        --no-psqlrc -t -A \
        -c "SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='${tbl}';" \
        2>/dev/null | grep -q '^1$'
}

# ---------------------------------------------------------------------------
# Export 1: query_gaps
# ---------------------------------------------------------------------------
GAPS_OUT="${SNAPSHOT_DIR}/query-gaps.jsonl"
GAPS_COUNT=0

if _table_exists "query_gaps"; then
    _export_jsonl "$GAPS_OUT" \
        "SELECT query_hash, query_text, score, collection
         FROM query_gaps
         ORDER BY query_text
         LIMIT 1000"
    GAPS_COUNT="$(wc -l < "$GAPS_OUT" | tr -d '[:space:]')"
else
    printf '{"note":"table_not_found","table":"query_gaps"}\n' > "$GAPS_OUT"
    printf 'export-ai-behavior-snapshot: query_gaps table not found — wrote placeholder\n' >&2
fi

# ---------------------------------------------------------------------------
# Export 2: imported_documents metadata (no content column — too large)
# ---------------------------------------------------------------------------
DOCS_OUT="${SNAPSHOT_DIR}/imported-documents-meta.jsonl"
DOCS_COUNT=0

if _table_exists "imported_documents"; then
    _export_jsonl "$DOCS_OUT" \
        "SELECT project, relative_path, title, content_type,
                source_trust_level, imported_at, modified_at
         FROM imported_documents
         ORDER BY imported_at DESC"
    DOCS_COUNT="$(wc -l < "$DOCS_OUT" | tr -d '[:space:]')"
else
    printf '{"note":"table_not_found","table":"imported_documents"}\n' > "$DOCS_OUT"
    printf 'export-ai-behavior-snapshot: imported_documents table not found — wrote placeholder\n' >&2
fi

# ---------------------------------------------------------------------------
# Export 3: hint adoption summary
# ---------------------------------------------------------------------------
HINT_OUT="${SNAPSHOT_DIR}/hint-adoption-summary.json"

if [[ -r "$HINT_AUDIT_LOG" ]]; then
    # Aggregate: count per hint_id + last_used timestamp via python3
    python3 - "$HINT_AUDIT_LOG" "$HINT_OUT" <<'PYEOF'
import json
import sys
from collections import defaultdict

audit_path = sys.argv[1]
out_path   = sys.argv[2]

counts    = defaultdict(int)
last_used = {}

with open(audit_path) as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        hint_id = rec.get("hint_id") or rec.get("id") or rec.get("rule_id")
        if not hint_id:
            continue
        counts[hint_id] += 1
        ts = rec.get("ts") or rec.get("timestamp") or rec.get("created_at")
        if ts and (hint_id not in last_used or ts > last_used[hint_id]):
            last_used[hint_id] = ts

summary = [
    {"hint_id": hid, "count": counts[hid], "last_used": last_used.get(hid)}
    for hid in sorted(counts, key=lambda h: -counts[h])
]
with open(out_path, "w") as fh:
    json.dump({"hints": summary, "total_entries": sum(counts.values())}, fh, indent=2)
PYEOF
else
    printf '{"note":"no_data"}\n' > "$HINT_OUT"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf 'export: %s query_gaps, %s documents exported\n' "$GAPS_COUNT" "$DOCS_COUNT"
printf 'export: snapshots written to %s\n' "$SNAPSHOT_DIR"
