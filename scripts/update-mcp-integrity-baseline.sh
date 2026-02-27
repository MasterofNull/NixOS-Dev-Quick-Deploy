#!/usr/bin/env bash
# Phase 12.4.2 — Update the MCP server source file integrity baseline.
# Run after every deployment (nixos-rebuild switch) to record current hashes.
set -euo pipefail

MCP_SERVER_DIR="${MCP_SERVER_DIR:-}"
if [[ -z "$MCP_SERVER_DIR" ]]; then
  MCP_SERVER_DIR="$(cd "$(dirname "$0")/.." && pwd)/ai-stack/mcp-servers"
fi

BASELINE_FILE="${MCP_INTEGRITY_BASELINE:-/var/lib/nixos-ai-stack/mcp-source-baseline.sha256}"

mkdir -p "$(dirname "$BASELINE_FILE")"
tmp=$(mktemp)

find "$MCP_SERVER_DIR" -name "*.py" -type f | sort | while read -r f; do
  sha256sum "$f"
done > "$tmp"

count=$(wc -l < "$tmp")
mv "$tmp" "$BASELINE_FILE"
echo "[mcp-integrity-baseline] Wrote $count file hashes to $BASELINE_FILE"
