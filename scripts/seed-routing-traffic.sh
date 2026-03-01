#!/usr/bin/env bash
# seed-routing-traffic.sh — send a batch of test queries through hybrid-coordinator
# to bootstrap routing, semantic cache, and eval metrics.
#
# Run after each nixos-rebuild switch or whenever §2/§3 show 0 events.
# Also called from nixos-quick-deploy.sh post-flight.
#
# Usage:
#   scripts/seed-routing-traffic.sh [--count N]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

COUNT="${1:-}"
QUERY_COUNT=6
while [[ $# -gt 0 ]]; do
  case "$1" in
    --count) QUERY_COUNT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

HYBRID_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
if [[ -r "$HYBRID_KEY_FILE" ]]; then
  HYBRID_KEY="${HYBRID_API_KEY:-$(tr -d '[:space:]' < "$HYBRID_KEY_FILE")}"
else
  HYBRID_KEY="${HYBRID_API_KEY:-}"
fi
if [[ -z "$HYBRID_KEY" ]]; then
  printf 'seed-routing-traffic: SKIP — no hybrid API key (set HYBRID_API_KEY)\n' >&2
  exit 0
fi

QUERIES=(
  "what is lib.mkForce in NixOS"
  "NixOS flake configuration basics"
  "how to use lib.mkIf in NixOS modules"
  "Qdrant vector database configuration"
  "how does the hybrid coordinator route queries"
  "NixOS systemd service options"
  "postgresql NixOS module setup"
  "how to write a NixOS home-manager module"
)

printf 'seed-routing-traffic: sending %d queries through hybrid-coordinator...\n' "$QUERY_COUNT"
PASS=0; FAIL=0
for i in "${!QUERIES[@]}"; do
  [[ $i -ge $QUERY_COUNT ]] && break
  Q="${QUERIES[$i]}"
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 30 --connect-timeout 5 \
    -X POST "${HYBRID_URL%/}/query" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${HYBRID_KEY}" \
    -d "{\"query\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$Q"),\"mode\":\"auto\",\"prefer_local\":true,\"limit\":3}" \
    2>/dev/null)
  if [[ "$HTTP_CODE" =~ ^2 ]]; then
    printf '  OK  %s\n' "$Q"
    (( PASS++ )) || true
  else
    printf '  FAIL HTTP %s: %s\n' "$HTTP_CODE" "$Q" >&2
    (( FAIL++ )) || true
  fi
done

printf 'seed-routing-traffic: %d OK, %d FAIL\n' "$PASS" "$FAIL"
