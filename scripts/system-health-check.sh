#!/usr/bin/env bash
set -euo pipefail

DETAILED=false
for arg in "$@"; do
  case "$arg" in
    --detailed|-v) DETAILED=true ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

fail=0
check_unit() {
  local unit="$1"
  if systemctl is-active --quiet "$unit"; then
    printf 'OK   %s\n' "$unit"
    return 0
  fi
  local status_rc=0
  systemctl status "$unit" >/dev/null 2>&1 || status_rc=$?
  if [[ "$status_rc" -eq 4 ]]; then
    return 0
  fi
  printf 'FAIL %s inactive\n' "$unit"
  fail=1
}

# Core declarative stack units
check_unit ai-stack.target
check_unit ai-aidb.service
check_unit ai-hybrid-coordinator.service
check_unit ai-ralph-wiggum.service
check_unit ai-aider-wrapper.service
check_unit ai-otel-collector.service
check_unit ai-switchboard.service
check_unit qdrant.service
check_unit llama-cpp.service
check_unit llama-cpp-embed.service
check_unit postgresql.service
check_unit redis-mcp.service
check_unit command-center-dashboard-api.service
check_unit command-center-dashboard-frontend.service
check_unit prometheus.service
check_unit prometheus-node-exporter.service

check_http() {
  local label="$1"
  local url="$2"
  if curl -fsS --max-time 5 --connect-timeout 3 "$url" >/dev/null 2>&1; then
    printf 'OK   %s\n' "$label"
  else
    printf 'FAIL %s unreachable (%s)\n' "$label" "$url"
    fail=1
  fi
}

check_http_json_field() {
  local label="$1"
  local url="$2"
  local jq_expr="$3"
  local expected="$4"
  local value=""
  if ! command -v jq >/dev/null 2>&1; then
    printf 'FAIL %s requires jq for JSON assertion\n' "$label"
    fail=1
    return
  fi
  if command -v jq >/dev/null 2>&1; then
    value="$(curl -fsS --max-time 5 --connect-timeout 3 "$url" 2>/dev/null | jq -r "$jq_expr" 2>/dev/null || true)"
  fi
  if [[ -n "$value" && "$value" == "$expected" ]]; then
    printf 'OK   %s\n' "$label"
  else
    printf 'FAIL %s expected=%s got=%s (%s)\n' "$label" "$expected" "${value:-unknown}" "$url"
    fail=1
  fi
}

check_http "Prometheus ready endpoint" "${PROMETHEUS_URL%/}/-/ready"
check_http "Dashboard API health endpoint" "${DASHBOARD_API_URL%/}/api/health"
check_http "Dashboard frontend endpoint" "${DASHBOARD_URL%/}/dashboard.html"
check_http_json_field "Dashboard aggregate health" "${DASHBOARD_API_URL%/}/api/health/aggregate" '.overall_status' 'healthy'
if systemctl list-unit-files --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "ai-switchboard.service"; then
  check_http_json_field "AI switchboard health" "${SWITCHBOARD_URL%/}/health" '.status' 'ok'
fi

if [[ "$DETAILED" == "true" ]]; then
  echo "-- Declarative runtime summary --"
  systemctl --no-pager --type=service --type=target | awk '/ai-stack|ai-aidb|ai-hybrid|ai-ralph|qdrant|llama-cpp|postgresql|redis-mcp|command-center-dashboard/ {print}' || true
fi

if [[ $fail -ne 0 ]]; then
  echo "Declarative health check failed." >&2
  exit 1
fi

echo "Declarative health check passed."
