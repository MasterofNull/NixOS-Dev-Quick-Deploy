#!/usr/bin/env bash
# Trim temporal_facts.json to the most recent N days.
# Runs as a NixOS systemd timer (daily). Safe to run manually.
#
# Usage: trim-temporal-facts.sh [--days N] [--dry-run]
#   --days N     Keep facts from the last N days (default: 30)
#   --dry-run    Print what would be removed without writing

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FACTS_FILE="${TEMPORAL_FACTS_FILE:-$REPO_ROOT/.aidb/temporal_facts.json}"
DAYS="${TEMPORAL_FACTS_RETENTION_DAYS:-30}"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --days)    DAYS="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *)         echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [[ ! -f "$FACTS_FILE" ]]; then
    echo "[trim-temporal-facts] $FACTS_FILE not found — nothing to trim"
    exit 0
fi

CUTOFF_EPOCH=$(date -d "$DAYS days ago" +%s 2>/dev/null || date -v "-${DAYS}d" +%s)
BEFORE=$(wc -c < "$FACTS_FILE")

python3 - "$FACTS_FILE" "$CUTOFF_EPOCH" "$DRY_RUN" <<'PYEOF'
import json, sys, os, time
from datetime import datetime, timezone

path, cutoff_str, dry_run_str = sys.argv[1], sys.argv[2], sys.argv[3]
cutoff = int(cutoff_str)
dry_run = dry_run_str.lower() == "true"

with open(path) as f:
    raw = f.read()

# Tolerate files with trailing garbage after the closing ] (common append-corruption)
_needs_rewrite = False
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(raw)
    _needs_rewrite = True
    print(f"[trim-temporal-facts] WARNING: file had trailing garbage — will rewrite cleanly")

if not isinstance(data, list):
    print(f"[trim-temporal-facts] Unexpected format (not a list) — skipping")
    sys.exit(0)

before = len(data)
kept = []
for fact in data:
    ts_raw = fact.get("timestamp") or fact.get("created_at") or fact.get("ts") or ""
    try:
        if isinstance(ts_raw, (int, float)):
            ts_epoch = int(ts_raw)
        else:
            dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            ts_epoch = int(dt.timestamp())
        if ts_epoch >= cutoff:
            kept.append(fact)
    except Exception:
        kept.append(fact)  # keep facts with unparseable timestamps

removed = before - len(kept)
if dry_run:
    print(f"[trim-temporal-facts] DRY-RUN: would remove {removed}/{before} facts older than {cutoff_str}")
    sys.exit(0)

if removed == 0 and not _needs_rewrite:
    print(f"[trim-temporal-facts] Nothing to trim ({before} facts all within {sys.argv[2]}s cutoff)")
    sys.exit(0)
elif removed == 0:
    print(f"[trim-temporal-facts] No facts expired; rewriting to fix corruption")

tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(kept, f, indent=2)
os.replace(tmp, path)
print(f"[trim-temporal-facts] Removed {removed}/{before} facts, kept {len(kept)}")
PYEOF

AFTER=$(wc -c < "$FACTS_FILE" 2>/dev/null || echo 0)
echo "[trim-temporal-facts] File size: before=${BEFORE}B after=${AFTER}B"
