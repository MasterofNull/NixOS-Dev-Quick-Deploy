#!/usr/bin/env bash
set -euo pipefail

DETAILED=false
for arg in "$@"; do
  case "$arg" in
    --detailed|-v) DETAILED=true ;;
  esac
done

fail=0
check_unit() {
  local unit="$1"
  if systemctl list-unit-files --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit"; then
    if systemctl is-active --quiet "$unit"; then
      printf 'OK   %s\n' "$unit"
    else
      printf 'FAIL %s inactive\n' "$unit"
      fail=1
    fi
  fi
}

# Core declarative stack units
check_unit ai-stack.target
check_unit ai-aidb.service
check_unit ai-hybrid-coordinator.service
check_unit ai-ralph-wiggum.service
check_unit qdrant.service
check_unit llama-cpp.service
check_unit llama-cpp-embed.service
check_unit postgresql.service
check_unit redis-mcp.service
check_unit command-center-dashboard.service

if [[ "$DETAILED" == "true" ]]; then
  echo "-- Declarative runtime summary --"
  systemctl --no-pager --type=service --type=target | awk '/ai-stack|ai-aidb|ai-hybrid|ai-ralph|qdrant|llama-cpp|postgresql|redis-mcp|command-center-dashboard/ {print}' || true
fi

if [[ $fail -ne 0 ]]; then
  echo "Declarative health check failed." >&2
  exit 1
fi

echo "Declarative health check passed."
