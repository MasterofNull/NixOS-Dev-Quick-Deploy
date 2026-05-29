#!/usr/bin/env bash
# Trim AI stack log files by timestamp TTL and delete stale delegation outputs.
# Prevents unbounded growth of high-throughput JSONL audit/telemetry logs.
#
# Configured via env vars (all have defaults); also called directly by the
# data-retention NixOS systemd timer.
#
# Usage: trim-ai-logs.sh [--dry-run]
#
# Env vars (all optional, have defaults):
#   AI_LOGS_AUDIT_SIDECAR_DAYS     — tool-audit.jsonl TTL (default: 7)
#   AI_LOGS_HINT_AUDIT_DAYS        — hint-audit.jsonl TTL (default: 7)
#   AI_LOGS_HYBRID_EVENTS_DAYS     — hybrid-events.jsonl TTL (default: 14)
#   AI_LOGS_DELEGATION_FEEDBACK_DAYS — delegation-feedback.jsonl TTL (default: 30)
#   AI_LOGS_DELEGATION_OUTPUTS_DAYS  — .agents/delegation/outputs/*.log TTL (default: 14)
#   AI_LOGS_USER_SPOOL_DAYS        — user-space hybrid-events spool TTL (default: 14)
#   REPO_ROOT                      — repo root path (default: auto-detected)

set -euo pipefail

DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

AUDIT_DAYS="${AI_LOGS_AUDIT_SIDECAR_DAYS:-7}"
HINT_AUDIT_DAYS="${AI_LOGS_HINT_AUDIT_DAYS:-7}"
HYBRID_EVENTS_DAYS="${AI_LOGS_HYBRID_EVENTS_DAYS:-14}"
DELEGATION_FEEDBACK_DAYS="${AI_LOGS_DELEGATION_FEEDBACK_DAYS:-30}"
DELEGATION_OUTPUTS_DAYS="${AI_LOGS_DELEGATION_OUTPUTS_DAYS:-14}"
USER_SPOOL_DAYS="${AI_LOGS_USER_SPOOL_DAYS:-14}"

# ── JSONL trimmer ─────────────────────────────────────────────────────────────
# Reuses the same timestamp-aware trim logic as trim-snapshots.sh.
trim_jsonl() {
    local file="$1"
    local days="$2"
    local label="${3:-$(basename "$file")}"

    if [[ ! -f "$file" ]]; then
        return 0
    fi
    if [[ ! -w "$file" ]]; then
        echo "[trim-ai-logs] SKIP $label — not writable (check group permissions)"
        return 0
    fi

    local cutoff_epoch
    cutoff_epoch=$(date -d "$days days ago" +%s 2>/dev/null || date -v "-${days}d" +%s)

    python3 - "$file" "$cutoff_epoch" "$DRY_RUN" "$label" <<'PYEOF'
import json, sys, os
from datetime import datetime, timezone

path, cutoff_str, dry_run_str, label = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
cutoff = int(cutoff_str)
dry_run = dry_run_str.lower() == "true"

lines_before = 0
lines_kept = []
with open(path, encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        lines_before += 1
        try:
            obj = json.loads(line)
            ts_raw = (
                obj.get("timestamp") or obj.get("created_at")
                or obj.get("ts") or obj.get("time") or ""
            )
            if isinstance(ts_raw, (int, float)):
                ts_epoch = int(ts_raw)
            else:
                dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                ts_epoch = int(dt.timestamp())
            if ts_epoch >= cutoff:
                lines_kept.append(line)
        except Exception:
            # Unparseable / no timestamp → keep (conservative)
            lines_kept.append(line)

removed = lines_before - len(lines_kept)
if dry_run:
    print(f"[trim-ai-logs] DRY-RUN {label}: would remove {removed}/{lines_before} lines")
    sys.exit(0)
if removed == 0:
    sys.exit(0)

import stat as _stat
# Capture original ownership + mode before replacing.
st = os.stat(path)
orig_uid, orig_gid = st.st_uid, st.st_gid
orig_mode = _stat.S_IMODE(st.st_mode)

tmp = path + ".trim.tmp"
try:
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_kept))
        if lines_kept:
            f.write("\n")
    os.replace(tmp, path)
    # Restore ownership + mode lost by os.replace (new inode is owned by writer).
    try:
        os.chown(path, orig_uid, orig_gid)
        os.chmod(path, orig_mode)
    except PermissionError:
        pass  # Not root — file already has correct ownership from same-user write
    print(f"[trim-ai-logs] {label}: removed {removed}/{lines_before} lines, kept {len(lines_kept)}")
except Exception as e:
    if os.path.exists(tmp):
        os.unlink(tmp)
    print(f"[trim-ai-logs] ERROR writing {label}: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

# ── Delegation outputs cleanup ────────────────────────────────────────────────
trim_delegation_outputs() {
    local dir="$1"
    local days="$2"

    if [[ ! -d "$dir" ]]; then
        return 0
    fi

    local count=0
    local removed=0
    while IFS= read -r -d '' f; do
        count=$((count + 1))
        if $DRY_RUN; then
            echo "[trim-ai-logs] DRY-RUN would delete: $(basename "$f")"
        else
            rm -f "$f"
            removed=$((removed + 1))
        fi
    done < <(find "$dir" -maxdepth 1 -type f \( -name "*.log" -o -name "*.json" \) -mtime "+${days}" -print0 2>/dev/null)

    if [[ $count -gt 0 ]]; then
        if $DRY_RUN; then
            echo "[trim-ai-logs] DRY-RUN delegation outputs: would delete $count files older than ${days}d"
        else
            echo "[trim-ai-logs] delegation outputs: deleted $removed files older than ${days}d"
        fi
    fi
}

# ── Target list ───────────────────────────────────────────────────────────────

# 1. Tool audit sidecar (highest volume — trim aggressively)
trim_jsonl \
    "/var/log/ai-audit-sidecar/tool-audit.jsonl" \
    "$AUDIT_DAYS" \
    "tool-audit.jsonl"

# 2. Hint audit log
trim_jsonl \
    "/var/log/nixos-ai-stack/hint-audit.jsonl" \
    "$HINT_AUDIT_DAYS" \
    "hint-audit.jsonl"

# 3. Service-side hybrid events (largest telemetry file)
trim_jsonl \
    "/var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl" \
    "$HYBRID_EVENTS_DAYS" \
    "hybrid-events.jsonl (service)"

# 4. Delegation feedback (longer TTL — used for failure analysis)
trim_jsonl \
    "/var/lib/ai-stack/hybrid/telemetry/delegation-feedback.jsonl" \
    "$DELEGATION_FEEDBACK_DAYS" \
    "delegation-feedback.jsonl"

# 5. User-space events spool (.agents/telemetry/)
trim_jsonl \
    "$REPO_ROOT/.agents/telemetry/hybrid-events.jsonl" \
    "$USER_SPOOL_DAYS" \
    "user-spool/hybrid-events.jsonl"

# 6. Delegation task output files
trim_delegation_outputs \
    "$REPO_ROOT/.agents/delegation/outputs" \
    "$DELEGATION_OUTPUTS_DAYS"

echo "[trim-ai-logs] done"
