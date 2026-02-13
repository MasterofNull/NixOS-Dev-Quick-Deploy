#!/usr/bin/env bash
# Verify local LLM usage + telemetry feedback loop.

set -euo pipefail

AIDB_URL="${AIDB_URL:-http://${SERVICE_HOST:-localhost}:8091}"
LLAMA_CPP_URL="${LLAMA_CPP_BASE_URL:-http://${SERVICE_HOST:-localhost}:8080}"
TELEMETRY_PATH="${AIDB_TELEMETRY_PATH:-$HOME/.local/share/nixos-ai-stack/telemetry/aidb-events.jsonl}"
HYBRID_TELEMETRY_PATH="${HYBRID_TELEMETRY_PATH:-$HOME/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl}"
AI_STACK_DATA="${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack}"
TELEMETRY_DIR="${AI_STACK_DATA}/telemetry"
TELEMETRY_STALE_MINUTES="${TELEMETRY_STALE_MINUTES:-30}"

info() { printf '\033[0;34m[INFO]\033[0m %s\n' "$*"; }
success() { printf '\033[0;32m[ OK ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }

stale_warning() {
  local label="$1"
  local timestamp="$2"
  local threshold_minutes="${3:-$TELEMETRY_STALE_MINUTES}"
  if [[ -z "$timestamp" ]]; then
    warn "${label} missing timestamp"
    return 0
  fi
  local epoch
  epoch=$(date -d "$timestamp" +%s 2>/dev/null || true)
  if [[ -z "$epoch" ]]; then
    warn "${label} invalid timestamp: $timestamp"
    return 0
  fi
  local now
  now=$(date +%s)
  local diff_minutes=$(( (now - epoch) / 60 ))
  if (( diff_minutes > threshold_minutes )); then
    warn "${label} stale (${diff_minutes}m > ${threshold_minutes}m)"
  fi
}

info "Checking llama.cpp health..."
if curl -sf --max-time 5 --connect-timeout 3 "${LLAMA_CPP_URL%/}/health" >/dev/null 2>&1; then
  success "llama.cpp reachable at ${LLAMA_CPP_URL%/}/health"
else
  warn "llama.cpp not reachable at ${LLAMA_CPP_URL%/}/health"
fi

info "Triggering AIDB telemetry probe (local LLM call)..."
if curl -sf --max-time 10 --connect-timeout 3 -X POST "$AIDB_URL/telemetry/probe" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Telemetry probe: confirm local LLM route.","max_tokens":32}' \
  >/dev/null; then
  success "AIDB telemetry probe executed"
else
  warn "AIDB telemetry probe failed (check AIDB service)"
fi

info "Reading telemetry summary..."
if curl -sf --max-time 5 --connect-timeout 3 "$AIDB_URL/telemetry/summary" | jq .; then
  success "Telemetry summary retrieved"
else
  warn "Telemetry summary unavailable"
fi

info "Checking telemetry log file..."
if [[ ! -d "$TELEMETRY_DIR" ]]; then
  mkdir -p "$TELEMETRY_DIR"
fi
if [[ -f "$TELEMETRY_PATH" ]]; then
  last_event=$(tail -n 1 "$TELEMETRY_PATH")
  echo "$last_event" | jq . || echo "$last_event"
  last_timestamp=$(echo "$last_event" | jq -r '.timestamp // .created_at // empty' 2>/dev/null || true)
  stale_warning "AIDB telemetry" "$last_timestamp"
  success "Latest AIDB telemetry event found"
else
  warn "Telemetry log missing at $TELEMETRY_PATH"
fi

info "Checking hybrid coordinator telemetry log..."
if [[ -f "$HYBRID_TELEMETRY_PATH" ]]; then
  last_event=$(tail -n 1 "$HYBRID_TELEMETRY_PATH")
  echo "$last_event" | jq . || echo "$last_event"
  last_timestamp=$(echo "$last_event" | jq -r '.timestamp // .created_at // empty' 2>/dev/null || true)
  stale_warning "Hybrid telemetry" "$last_timestamp"
  success "Latest hybrid telemetry event found"
else
  warn "Hybrid telemetry log missing at $HYBRID_TELEMETRY_PATH"
  warn "Trigger hybrid telemetry by calling the MCP tool 'track_interaction' or 'augment_query'."
fi

info "Done."
