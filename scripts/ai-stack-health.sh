#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

required_units=(
  ai-stack.target
  ai-aidb.service
  ai-hybrid-coordinator.service
  ai-ralph-wiggum.service
  ai-otel-collector.service
  ai-switchboard.service
  qdrant.service
  llama-cpp.service
  llama-cpp-embed.service
  postgresql.service
  redis-mcp.service
  prometheus.service
  prometheus-node-exporter.service
  command-center-dashboard-api.service
  command-center-dashboard-frontend.service
)

missing=0
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
  printf 'FAIL %s (inactive)\n' "$unit"
  missing=1
}

for unit in "${required_units[@]}"; do
  check_unit "$unit"
done

check_http() {
  local label="$1"
  local url="$2"
  if curl -fsS --max-time 5 --connect-timeout 3 "$url" >/dev/null 2>&1; then
    printf 'OK   %s\n' "$label"
  else
    printf 'FAIL %s unreachable (%s)\n' "$label" "$url"
    missing=1
  fi
}

check_http "Prometheus ready endpoint" "${PROMETHEUS_URL%/}/-/ready"
check_http "Dashboard API health endpoint" "${DASHBOARD_API_URL%/}/api/health"
check_http "Dashboard frontend endpoint" "${DASHBOARD_URL%/}/dashboard.html"
if systemctl list-unit-files --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "ai-switchboard.service"; then
  check_http "AI switchboard health endpoint" "${SWITCHBOARD_URL%/}/health"
fi

if [[ $missing -ne 0 ]]; then
  echo "One or more declarative AI stack checks failed (unit state or HTTP health)." >&2
  exit 1
fi

echo "Declarative AI stack health checks passed."
