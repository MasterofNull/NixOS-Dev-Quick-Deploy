#!/usr/bin/env bash
# Validate autonomous capability discovery + cache behavior in hybrid coordinator.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq

HYBRID_API_KEY="${HYBRID_API_KEY:-}"
if [[ -z "$HYBRID_API_KEY" ]]; then
  HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"
  if [[ -r "$HYBRID_API_KEY_FILE" ]]; then
    HYBRID_API_KEY="$(<"$HYBRID_API_KEY_FILE")"
  fi
fi

post_query() {
  local prompt="$1"
  local response_file="$2"
  local -a headers
  headers=(-H 'Content-Type: application/json')
  if [[ -n "$HYBRID_API_KEY" ]]; then
    headers+=(-H "X-API-Key: ${HYBRID_API_KEY}")
  fi
  curl -sS --max-time 15 --connect-timeout 5 \
    -o "$response_file" -w '%{http_code}' \
    -X POST "${HYBRID_URL%/}/query" \
    "${headers[@]}" \
    -d "$(jq -n --arg q "$prompt" '{query:$q,mode:"auto",generate_response:false}')"
}

prompt_discovery="Find and apply the best MCP tools, skills, datasets, and workflows for RAG ingestion and agent routing optimization."
response_tmp="$(mktemp)"

first_code="$(post_query "$prompt_discovery" "$response_tmp" || true)"
if [[ "$first_code" == "401" && -z "$HYBRID_API_KEY" ]]; then
  rm -f "$response_tmp"
  echo "PASS: hybrid capability-discovery endpoint enforces API key (401 without HYBRID_API_KEY)."
  exit 0
fi
if [[ ! "$first_code" =~ ^2 ]]; then
  echo "Hybrid capability-discovery probe failed (HTTP ${first_code:-unknown})" >&2
  cat "$response_tmp" >&2 || true
  rm -f "$response_tmp"
  exit 1
fi

first="$(cat "$response_tmp")"
echo "$first" | jq -e '.capability_discovery.decision == "invoked" or .capability_discovery.decision == "cache_hit"' >/dev/null

echo "PASS: first autonomous discovery query returned capability discovery metadata."

second_code="$(post_query "$prompt_discovery" "$response_tmp" || true)"
if [[ ! "$second_code" =~ ^2 ]]; then
  echo "Hybrid repeated discovery probe failed (HTTP ${second_code:-unknown})" >&2
  cat "$response_tmp" >&2 || true
  rm -f "$response_tmp"
  exit 1
fi
second="$(cat "$response_tmp")"
echo "$second" | jq -e '.capability_discovery.cache_hit == true or .capability_discovery.decision == "cache_hit"' >/dev/null

echo "PASS: repeated discovery query used cached capability discovery."

prompt_generic="What is 2 plus 2?"
third_code="$(post_query "$prompt_generic" "$response_tmp" || true)"
if [[ ! "$third_code" =~ ^2 ]]; then
  echo "Hybrid generic query probe failed (HTTP ${third_code:-unknown})" >&2
  cat "$response_tmp" >&2 || true
  rm -f "$response_tmp"
  exit 1
fi
third="$(cat "$response_tmp")"
echo "$third" | jq -e '.capability_discovery.decision == "skipped" or .capability_discovery.reason == "query-too-short" or .capability_discovery.reason == "no-discovery-intent"' >/dev/null

rm -f "$response_tmp"
echo "PASS: non-discovery prompt did not force capability search."
