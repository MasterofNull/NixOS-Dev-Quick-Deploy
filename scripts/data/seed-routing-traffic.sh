#!/usr/bin/env bash
# seed-routing-traffic.sh — send a batch of test queries through hybrid-coordinator
# to bootstrap routing, semantic cache, and eval metrics.
#
# Run after each nixos-rebuild switch or whenever §2/§3 show 0 events.
# Also called from nixos-quick-deploy.sh post-flight.
#
# Usage:
#   scripts/data/seed-routing-traffic.sh [--count N]
#   scripts/data/seed-routing-traffic.sh --count 8 --replay 2 --include-gaps
#   SEED_ROUTING_SKIP_GENERATION=true scripts/data/seed-routing-traffic.sh --count N
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../../../config/service-endpoints.sh"

COUNT="${1:-}"
QUERY_COUNT=6
REPLAY_COUNT=1
INCLUDE_GAPS="${SEED_ROUTING_INCLUDE_GAPS:-true}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --count) QUERY_COUNT="$2"; shift 2 ;;
    --replay) REPLAY_COUNT="$2"; shift 2 ;;
    --include-gaps) INCLUDE_GAPS=true; shift ;;
    --no-gaps) INCLUDE_GAPS=false; shift ;;
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

BASE_QUERIES=(
  "what is lib.mkForce in NixOS"
  "NixOS flake configuration basics"
  "how to use lib.mkIf in NixOS modules"
  "Qdrant vector database configuration"
  "how does the hybrid coordinator route queries"
  "NixOS systemd service options"
  "postgresql NixOS module setup"
  "how to write a NixOS home-manager module"
)

declare -a DYNAMIC_GAP_QUERIES=()
if [[ "${INCLUDE_GAPS}" == "true" ]] && command -v psql >/dev/null 2>&1; then
  PG_PASS_FILE="${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}"
  PG_HOST="${POSTGRES_HOST:-127.0.0.1}"
  PG_PORT="${POSTGRES_PORT:-5432}"
  PG_USER="${POSTGRES_USER:-aidb}"
  PG_DB="${POSTGRES_DB:-aidb}"
  if [[ -r "${PG_PASS_FILE}" ]]; then
    export PGPASSWORD="$(tr -d '[:space:]' < "${PG_PASS_FILE}")"
  fi
  GAP_ROWS="$(psql -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" -d "${PG_DB}" -t -A \
    -c "SELECT query_text FROM query_gaps GROUP BY query_text ORDER BY COUNT(*) DESC LIMIT 6;" \
    2>/dev/null || true)"
  while IFS= read -r row; do
    q="$(echo "${row}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -n "${q}" ]] || continue
    DYNAMIC_GAP_QUERIES+=("${q}")
  done <<< "${GAP_ROWS}"
fi

declare -a QUERIES=("${BASE_QUERIES[@]}")
for q in "${DYNAMIC_GAP_QUERIES[@]}"; do
  duplicate=false
  for b in "${QUERIES[@]}"; do
    if [[ "${b}" == "${q}" ]]; then
      duplicate=true
      break
    fi
  done
  [[ "${duplicate}" == true ]] || QUERIES+=("${q}")
done

printf 'seed-routing-traffic: sending %d queries x %d replay through hybrid-coordinator...\n' "$QUERY_COUNT" "$REPLAY_COUNT"
PASS=0; FAIL=0
for ((r=1; r<=REPLAY_COUNT; r++)); do
  for i in "${!QUERIES[@]}"; do
    [[ $i -ge $QUERY_COUNT ]] && break
    Q="${QUERIES[$i]}"
    HTTP_CODE="$(curl -s -o /dev/null -w "%{http_code}" \
      --max-time 30 --connect-timeout 5 \
      -X POST "${HYBRID_URL%/}/query" \
      -H "Content-Type: application/json" \
      -H "X-API-Key: ${HYBRID_KEY}" \
      -d "{\"query\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$Q"),\"mode\":\"auto\",\"prefer_local\":true,\"limit\":3,\"context\":{\"skip_gap_tracking\":true,\"source\":\"seed-routing-traffic\"}}" \
      2>/dev/null || true)"
    [[ -n "$HTTP_CODE" ]] || HTTP_CODE="000"
    if [[ "$HTTP_CODE" =~ ^2 ]]; then
      printf '  OK  [pass %d] %s\n' "$r" "$Q"
      (( PASS++ )) || true
    else
      printf '  FAIL HTTP %s [pass %d]: %s\n' "$HTTP_CODE" "$r" "$Q" >&2
      (( FAIL++ )) || true
    fi
  done
done

printf 'seed-routing-traffic: %d OK, %d FAIL\n' "$PASS" "$FAIL"

if [[ "${SEED_ROUTING_SKIP_GENERATION:-false}" == "true" ]]; then
  printf 'seed-routing-traffic: generation seed skipped (SEED_ROUTING_SKIP_GENERATION=true)\n'
  exit 0
fi

# Send one short generation query to seed the backend-selection metric (§2).
# Uses generate_response=true so hybrid-coordinator calls the LLM and increments
# hybrid_llm_backend_selections_total.  max_tokens=32 keeps it fast even on
# CPU-only llama.cpp.  Non-blocking: failure is silently ignored.
GEN_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  --max-time 120 --connect-timeout 5 \
  -X POST "${HYBRID_URL%/}/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${HYBRID_KEY}" \
  -d '{"query":"what is NixOS","mode":"auto","prefer_local":true,"limit":1,"generate_response":true,"max_tokens":32,"context":{"skip_gap_tracking":true,"source":"seed-routing-traffic"}}' \
  2>/dev/null) || GEN_CODE="000"
if [[ "$GEN_CODE" =~ ^2 ]]; then
  printf 'seed-routing-traffic: backend-selection seeded (HTTP %s)\n' "$GEN_CODE"
else
  printf 'seed-routing-traffic: backend-selection seed skipped (HTTP %s)\n' "$GEN_CODE" >&2
fi
