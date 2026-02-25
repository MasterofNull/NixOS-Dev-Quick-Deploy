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
  local -a headers
  headers=(-H 'Content-Type: application/json')
  if [[ -n "$HYBRID_API_KEY" ]]; then
    headers+=(-H "X-API-Key: ${HYBRID_API_KEY}")
  fi
  curl -fsS --max-time 15 --connect-timeout 5 \
    -X POST "${HYBRID_URL%/}/query" \
    "${headers[@]}" \
    -d "$(jq -n --arg q "$prompt" '{query:$q,mode:"auto",generate_response:false}')"
}

prompt_discovery="Find and apply the best MCP tools, skills, datasets, and workflows for RAG ingestion and agent routing optimization."

first="$(post_query "$prompt_discovery")"
echo "$first" | jq -e '.capability_discovery.decision == "invoked" or .capability_discovery.decision == "cache_hit"' >/dev/null

echo "PASS: first autonomous discovery query returned capability discovery metadata."

second="$(post_query "$prompt_discovery")"
echo "$second" | jq -e '.capability_discovery.cache_hit == true or .capability_discovery.decision == "cache_hit"' >/dev/null

echo "PASS: repeated discovery query used cached capability discovery."

prompt_generic="What is 2 plus 2?"
third="$(post_query "$prompt_generic")"
echo "$third" | jq -e '.capability_discovery.decision == "skipped" or .capability_discovery.reason == "query-too-short" or .capability_discovery.reason == "no-discovery-intent"' >/dev/null

echo "PASS: non-discovery prompt did not force capability search."
