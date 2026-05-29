#!/usr/bin/env bash
# Trim JSONL snapshot files in ai-stack/snapshots/ to the last N days.
# Runs as a NixOS systemd timer (daily). Safe to run manually.
#
# Usage: trim-snapshots.sh [--days N] [--dry-run]
#   --days N     Keep entries from the last N days (default: 7)
#   --dry-run    Print what would be removed without writing

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SNAPSHOTS_DIR="${SNAPSHOTS_DIR:-$REPO_ROOT/ai-stack/snapshots}"
DAYS="${SNAPSHOTS_RETENTION_DAYS:-7}"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --days)    DAYS="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *)         echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [[ ! -d "$SNAPSHOTS_DIR" ]]; then
    echo "[trim-snapshots] $SNAPSHOTS_DIR not found — nothing to trim"
    exit 0
fi

CUTOFF_EPOCH=$(date -d "$DAYS days ago" +%s 2>/dev/null || date -v "-${DAYS}d" +%s)

trim_jsonl() {
    local file="$1"
    python3 - "$file" "$CUTOFF_EPOCH" "$DRY_RUN" <<'PYEOF'
import json, sys, os
from datetime import datetime, timezone

path, cutoff_str, dry_run_str = sys.argv[1], sys.argv[2], sys.argv[3]
cutoff = int(cutoff_str)
dry_run = dry_run_str.lower() == "true"

lines_before, lines_kept = 0, []
with open(path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        lines_before += 1
        try:
            obj = json.loads(line)
            ts_raw = obj.get("timestamp") or obj.get("created_at") or obj.get("ts") or ""
            if isinstance(ts_raw, (int, float)):
                ts_epoch = int(ts_raw)
            else:
                dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                ts_epoch = int(dt.timestamp())
            if ts_epoch >= cutoff:
                lines_kept.append(line)
        except Exception:
            lines_kept.append(line)

removed = lines_before - len(lines_kept)
fname = os.path.basename(path)
if dry_run:
    print(f"[trim-snapshots] DRY-RUN {fname}: would remove {removed}/{lines_before} lines")
    sys.exit(0)
if removed == 0:
    sys.exit(0)

import stat as _stat
st = os.stat(path)
orig_uid, orig_gid = st.st_uid, st.st_gid
orig_mode = _stat.S_IMODE(st.st_mode)

tmp = path + ".tmp"
with open(tmp, "w") as f:
    f.write("\n".join(lines_kept))
    if lines_kept:
        f.write("\n")
os.replace(tmp, path)
try:
    os.chown(path, orig_uid, orig_gid)
    os.chmod(path, orig_mode)
except PermissionError:
    pass
print(f"[trim-snapshots] {fname}: removed {removed}/{lines_before} lines, kept {len(lines_kept)}")
PYEOF
}

FOUND=0
for jsonl_file in "$SNAPSHOTS_DIR"/*.jsonl; do
    [[ -f "$jsonl_file" ]] || continue
    FOUND=$((FOUND + 1))
    trim_jsonl "$jsonl_file"
done

if [[ $FOUND -eq 0 ]]; then
    echo "[trim-snapshots] No .jsonl files found in $SNAPSHOTS_DIR"
fi
