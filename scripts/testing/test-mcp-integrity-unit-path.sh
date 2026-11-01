#!/usr/bin/env bash
# Regression: ai-mcp-integrity-check must declare jq + coreutils on its unit PATH.
# Without `path`, the alert branch of check-mcp-integrity.sh exits 127 (jq not found).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODULE="$REPO_ROOT/nix/modules/services/mcp-servers.nix"

block=$(awk '
  /systemd\.services\.ai-mcp-integrity-check = \{/ { inblock = 1 }
  inblock { print }
  inblock && /systemd\.timers\.ai-mcp-integrity-check/ { exit }
' "$MODULE")

if [[ -z "$block" ]]; then
  echo "FAIL: systemd.services.ai-mcp-integrity-check block not found in $MODULE" >&2
  exit 1
fi

status=0
for pkg in pkgs.jq pkgs.coreutils; do
  if [[ "$block" != *"$pkg"* ]]; then
    echo "FAIL: ai-mcp-integrity-check block lacks $pkg in path = [...]" >&2
    status=1
  fi
done

if [[ "$status" -eq 0 ]]; then
  echo "PASS: ai-mcp-integrity-check unit declares pkgs.jq and pkgs.coreutils"
fi
exit "$status"
