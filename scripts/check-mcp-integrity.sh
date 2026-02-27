#!/usr/bin/env bash
# Phase 12.4.2 — MCP server source file integrity check.
# Compares current sha256 hashes of all .py files under MCP_SERVER_DIR
# against a stored baseline. Writes a JSON alert if any file changed.
# Run hourly via systemd timer (see nix/modules/services/mcp-servers.nix).
set -euo pipefail

MCP_SERVER_DIR="${MCP_SERVER_DIR:-}"
if [[ -z "$MCP_SERVER_DIR" ]]; then
  # Try to locate the repo relative to this script
  MCP_SERVER_DIR="$(cd "$(dirname "$0")/.." && pwd)/ai-stack/mcp-servers"
fi

BASELINE_FILE="${MCP_INTEGRITY_BASELINE:-/var/lib/nixos-ai-stack/mcp-source-baseline.sha256}"
ALERT_DIR="${MCP_INTEGRITY_ALERT_DIR:-/var/lib/nixos-ai-stack/alerts}"

if [[ ! -f "$BASELINE_FILE" ]]; then
  echo "[mcp-integrity] No baseline at $BASELINE_FILE — skipping check (run scripts/update-mcp-integrity-baseline.sh first)" >&2
  exit 0
fi

changed_files=()
missing_files=()

while IFS=" " read -r expected_hash filepath; do
  [[ -z "$expected_hash" || -z "$filepath" ]] && continue
  if [[ ! -f "$filepath" ]]; then
    missing_files+=("$filepath")
    continue
  fi
  actual_hash=$(sha256sum "$filepath" | cut -d' ' -f1)
  if [[ "$actual_hash" != "$expected_hash" ]]; then
    changed_files+=("$filepath")
  fi
done < "$BASELINE_FILE"

if [[ "${#changed_files[@]}" -eq 0 && "${#missing_files[@]}" -eq 0 ]]; then
  echo "[mcp-integrity] PASS — all $(wc -l < "$BASELINE_FILE") source files match baseline"
  exit 0
fi

# Write alert
mkdir -p "$ALERT_DIR"
alert_file="$ALERT_DIR/mcp-integrity-$(date +%Y%m%d-%H%M%S).json"
changed_json=$(printf '%s\n' "${changed_files[@]+"${changed_files[@]}"}" | jq -R . | jq -s .)
missing_json=$(printf '%s\n' "${missing_files[@]+"${missing_files[@]}"}" | jq -R . | jq -s .)
cat > "$alert_file" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "alert": "mcp_source_integrity_violation",
  "changed_files": ${changed_json},
  "missing_files": ${missing_json}
}
EOF

echo "[mcp-integrity] ALERT: ${#changed_files[@]} changed, ${#missing_files[@]} missing — wrote $alert_file" >&2
if command -v notify-send &>/dev/null; then
  notify-send -u critical "AI Stack Integrity Alert" \
    "${#changed_files[@]} MCP source files changed, ${#missing_files[@]} missing"
fi
exit 1
