#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
mkdir -p "$RESULTS_DIR"

API_KEY_FILE="${AI_STACK_API_KEY_FILE:-ai-stack/kubernetes/secrets/generated/stack_api_key}"
if [[ -f "$API_KEY_FILE" ]]; then
  export AI_STACK_API_KEY="$(cat "$API_KEY_FILE")"
fi

export AIDB_BASE_URL="${AIDB_BASE_URL:-http://localhost:8091}"
export EMBEDDINGS_BASE_URL="${EMBEDDINGS_BASE_URL:-http://localhost:8081}"
export HYBRID_BASE_URL="${HYBRID_BASE_URL:-http://localhost:8092}"

locust -f "${SCRIPT_DIR}/locustfile.py" \
  --headless \
  -u 100 -r 10 -t 1m \
  --csv "${RESULTS_DIR}/ai-stack" \
  --logfile "${RESULTS_DIR}/ai-stack.log"
