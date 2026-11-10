#!/usr/bin/env bash
# Phase 12.4.2 — Update the MCP server source file integrity baseline.
# Run after every deployment (nixos-rebuild switch) to record current hashes.
set -euo pipefail

MCP_SERVER_DIR="${MCP_SERVER_DIR:-}"
if [[ -z "$MCP_SERVER_DIR" ]]; then
  MCP_SERVER_DIR="$(cd "$(dirname "$0")/../.." && pwd)/ai-stack/mcp-servers"
fi

BASELINE_FILE="${MCP_INTEGRITY_BASELINE:-/var/lib/nixos-ai-stack/mcp-source-baseline.sha256}"

mkdir -p "$(dirname "$BASELINE_FILE")"
tmp=$(mktemp)

find "$MCP_SERVER_DIR" -name "*.py" -type f -print0 | sort -z | while IFS= read -r -d '' f; do
  sha256sum "$f"
done > "$tmp"

count=$(wc -l < "$tmp")
if [[ "$count" -eq 0 ]]; then
  # Never replace an existing baseline with an empty one: it would verify nothing.
  rm -f "$tmp"
  echo "[mcp-integrity-baseline] ERROR: no .py files found under $MCP_SERVER_DIR - baseline $BASELINE_FILE NOT updated" >&2
  exit 1
fi
AUDIT_LOG="${MCP_INTEGRITY_AUDIT_LOG:-$(dirname "$BASELINE_FILE")/mcp-baseline-audit.jsonl}"
python3 - "$BASELINE_FILE" "$tmp" "$AUDIT_LOG" <<'PY_AUDIT'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def hashes(path):
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text().splitlines():
        digest, separator, name = line.partition("  ")
        if not separator:
            raise ValueError(f"Invalid baseline entry in {path}")
        if digest.startswith("\\"):
            digest = digest[1:]
            # GNU sha256sum escapes backslashes and newlines in filenames.
            decoded = []
            i = 0
            while i < len(name):
                if name[i] == "\\":
                    i += 1
                    decoded.append({"n": "\n", "r": "\r", "\\": "\\"}[name[i]])
                else:
                    decoded.append(name[i])
                i += 1
            name = "".join(decoded)
        result[name] = digest
    return result


old, new = (hashes(Path(p)) for p in sys.argv[1:3])
diff = {
    "changed": sorted(p for p in old.keys() & new.keys() if old[p] != new[p]),
    "added": sorted(new.keys() - old.keys()),
    "removed": sorted(old.keys() - new.keys()),
}
counts = {kind: len(paths) for kind, paths in diff.items()}
record = {
    "ts": datetime.now(timezone.utc).isoformat(),
    "actor": os.environ.get("SUDO_USER") or os.environ.get("USER", "unknown"),
    "git_rev": os.environ.get("MCP_BASELINE_GIT_REV", ""),
    **diff,
    "counts": counts,
}
audit = Path(sys.argv[3])
audit.parent.mkdir(parents=True, exist_ok=True)
with audit.open("a") as stream:
    stream.write(json.dumps(record, sort_keys=True) + "\n")
    stream.flush()
    os.fsync(stream.fileno())
print("[mcp-integrity-baseline] Audit: " + ", ".join(f"{n} {k}" for k, n in counts.items()))
for kind, path in [(kind, path) for kind, paths in diff.items() for path in paths][:10]:
    print(f"[mcp-integrity-baseline] {kind}: {json.dumps(path)}")
PY_AUDIT
# Install with 0644 so the DynamicUser integrity-check service can read it
install -m 644 "$tmp" "$BASELINE_FILE"
rm -f "$tmp"
echo "[mcp-integrity-baseline] Wrote $count file hashes to $BASELINE_FILE"
