#!/usr/bin/env bash
# check-dashboard-managed-service.sh — verify Command Center is served by systemd on loopback.
set -euo pipefail

SERVICE="${DASHBOARD_SERVICE:-command-center-dashboard-api.service}"
PORT="${DASHBOARD_API_PORT:-8889}"
HOST="${DASHBOARD_API_HOST:-127.0.0.1}"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "SKIP: systemctl unavailable"
  exit 0
fi

if ! systemctl list-unit-files "${SERVICE}" --no-legend 2>/dev/null | grep -q "${SERVICE}"; then
  echo "SKIP: ${SERVICE} is not installed on this host"
  exit 0
fi

if [[ "$(systemctl is-active "${SERVICE}" || true)" != "active" ]]; then
  echo "FAIL: ${SERVICE} is not active" >&2
  systemctl status "${SERVICE}" --no-pager -l | sed -n '1,80p' >&2 || true
  exit 1
fi

if ! command -v ss >/dev/null 2>&1; then
  echo "SKIP: ss unavailable"
  exit 0
fi

listeners="$(ss -ltnp "sport = :${PORT}" 2>/dev/null || true)"
if ! grep -q "${HOST}:${PORT}" <<<"${listeners}"; then
  echo "FAIL: dashboard is not listening on ${HOST}:${PORT}" >&2
  echo "${listeners}" >&2
  exit 1
fi

if grep -q "0.0.0.0:${PORT}" <<<"${listeners}"; then
  echo "FAIL: dashboard has an unmanaged/wide bind on 0.0.0.0:${PORT}" >&2
  echo "${listeners}" >&2
  exit 1
fi

if ! curl -sf "http://${HOST}:${PORT}/api/health" >/dev/null; then
  echo "FAIL: dashboard /api/health does not respond" >&2
  exit 1
fi

echo "PASS: ${SERVICE} active and serving ${HOST}:${PORT}"
