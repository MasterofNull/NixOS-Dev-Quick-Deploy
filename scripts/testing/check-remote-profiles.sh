#!/usr/bin/env bash
# Purpose: smoke gate for remote switchboard profile availability (Phase 8.3).
# Validates that remote profiles are visible in switchboard health — a prerequisite
# for enabling remote routing. Warn-only: remote routing is deliberately disabled
# (prefer_local=true) on this hardware-constrained deployment.
set -euo pipefail

SWB_URL="${SWB_URL:-http://127.0.0.1:8085}"

pass() { printf 'PASS: %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

http_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${SWB_URL}/health" 2>/dev/null || true)"
if [[ "$http_code" != "200" ]]; then
  printf 'SKIP: switchboard not reachable (http=%s)\n' "$http_code"
  exit 0
fi

body="$(curl -s --max-time 5 "${SWB_URL}/health" 2>/dev/null)"

remote_configured="$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('remote_configured','false'))" "$body" 2>/dev/null || echo false)"
remote_profile_count="$(python3 -c "
import json,sys
d=json.loads(sys.argv[1])
profiles=d.get('profiles') or {}
print(sum(1 for k in profiles if k.startswith('remote-')))
" "$body" 2>/dev/null || echo 0)"

if [[ "$remote_configured" != "True" && "$remote_configured" != "true" ]]; then
  warn "remote_configured=false — remote routing unavailable (expected on local-only deployments)"
fi

if [[ "$remote_profile_count" -eq 0 ]]; then
  warn "no remote-* profiles found in switchboard — remote routing requires profile configuration"
else
  pass "switchboard has ${remote_profile_count} remote profile(s) (remote_configured=${remote_configured})"
fi
