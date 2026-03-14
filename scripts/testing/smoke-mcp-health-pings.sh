#!/usr/bin/env bash
# Phase 11.2 — MCP Health Ping Protocol smoke test

set -euo pipefail

echo "=== MCP Health Ping Protocol Smoke Test ==="

PASS=0
FAIL=0

# Test individual health endpoints
for srv in "hybrid-coordinator:8003" "aidb:8002" "ralph-wiggum:8004"; do
  name="${srv%%:*}"
  port="${srv##*:}"
  echo -n "Testing $name /health ... "
  if curl -sS "http://127.0.0.1:$port/health" 2>/dev/null | jq -e '.status' >/dev/null 2>&1; then
    echo "PASS"
    ((PASS++))
  else
    echo "FAIL"
    ((FAIL++))
  fi
done

# Test health aggregate
echo -n "Testing /health/aggregate ... "
if curl -sS "http://127.0.0.1:8003/health/aggregate" 2>/dev/null | jq -e '.servers' >/dev/null 2>&1; then
  echo "PASS"
  ((PASS++))
else
  echo "FAIL"
  ((FAIL++))
fi

# Test aggregate latency tracking
echo -n "Verifying latency tracking ... "
if curl -sS "http://127.0.0.1:8003/health/aggregate" 2>/dev/null | jq -e '.servers["aidb"].latency_ms' >/dev/null 2>&1; then
  echo "PASS"
  ((PASS++))
else
  echo "FAIL"
  ((FAIL++))
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
