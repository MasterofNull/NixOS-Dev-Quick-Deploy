#!/usr/bin/env bash
set -euo pipefail

required_units=(
  ai-stack.target
  ai-aidb.service
  ai-hybrid-coordinator.service
  ai-ralph-wiggum.service
  qdrant.service
  llama-cpp.service
  llama-cpp-embed.service
  postgresql.service
  redis-mcp.service
)

missing=0
for unit in "${required_units[@]}"; do
  if systemctl list-unit-files --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit"; then
    if systemctl is-active --quiet "$unit"; then
      printf 'OK   %s\n' "$unit"
    else
      printf 'FAIL %s (inactive)\n' "$unit"
      missing=1
    fi
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "One or more declarative AI stack units are inactive." >&2
  exit 1
fi

echo "Declarative AI stack health checks passed."
