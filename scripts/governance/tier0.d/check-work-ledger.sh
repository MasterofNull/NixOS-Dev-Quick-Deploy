#!/usr/bin/env bash
# tier0.d: the durable work ledger must be readable. A needs-attention (corrupt) entry fails closed; a stale
# heartbeat is a time-class signal and only warns (Rule 19). Honors AQ_DELEGATION_DIR. Read-only.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TAG="[tier0.d/check-work-ledger]"

# `check` exits 1 when it reports problems; the verdict below comes from the report itself.
rc=0
report="$(python3 "$REPO_ROOT/scripts/ai/aq-ledger" check --json)" || rc=$?
if [[ "$rc" -gt 1 ]]; then
    echo "$TAG FAIL: aq-ledger check could not run (exit $rc)"
    exit 1
fi

python3 -c '
import json, sys

tag = sys.argv[1]

def clean(value):
    return "".join(c if c.isprintable() else "?" for c in str(value))

try:
    report = json.load(sys.stdin)
    checked, problems = report["checked"], report["problems"]
    broken = [p for p in problems if p["status"] == "needs-attention"]
    stale = [p for p in problems if p["stale_heartbeat"]]
except (ValueError, KeyError, TypeError) as exc:
    print(f"{tag} FAIL: unusable aq-ledger report ({type(exc).__name__})")
    sys.exit(1)
for entry in stale:
    print(tag, "WARN: stale heartbeat:", clean(entry["id"]), clean(entry["path"]))
for entry in broken:
    print(tag, "FAIL: needs-attention:", clean(entry["id"]), clean(entry["path"]))
    for warning in entry["warnings"]:
        print(f"{tag}   {clean(warning)}")
if broken:
    sys.exit(1)
print(f"{tag} PASS ({checked} entries)")
' "$TAG" <<<"$report"
