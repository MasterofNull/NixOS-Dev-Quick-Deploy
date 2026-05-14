#!/usr/bin/env bash
# aidb-reindex.sh — periodic AIDB knowledge re-indexer
#
# Runs two jobs in sequence:
#   1. aq-index-logic-patterns  — cross-cutting code patterns → logic-patterns project
#   2. ingest-project-knowledge.py — chunked docs → nixos-dev-quick-deploy project
#
# Driven by ai-aidb-reindex.service / ai-aidb-reindex.timer.
# Also safe to run manually: scripts/automation/aidb-reindex.sh
#
# Env vars (injected by systemd unit):
#   REPO_ROOT          — repo root path
#   AIDB_URL           — AIDB base URL (default http://127.0.0.1:8002)
#   AIDB_API_KEY_FILE  — secret file path (default /run/secrets/aidb_api_key)
#   INGEST_DELAY       — seconds between POST /documents calls (default 0.3)
#   REINDEX_OUTPUT     — JSON result file path (optional)

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
AIDB_API_KEY_FILE="${AIDB_API_KEY_FILE:-/run/secrets/aidb_api_key}"
INGEST_DELAY="${INGEST_DELAY:-0.3}"
REINDEX_OUTPUT="${REINDEX_OUTPUT:-}"
START_TS=$(date +%s)

log() { printf '[aidb-reindex] %s\n' "$*"; }
warn() { printf '[aidb-reindex] WARN: %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# Preflight: AIDB must be reachable
# ---------------------------------------------------------------------------
log "checking AIDB at ${AIDB_URL} …"
if ! curl -sf --max-time 5 "${AIDB_URL}/health" >/dev/null 2>&1; then
  warn "AIDB not reachable — skipping re-index run"
  exit 0
fi
log "AIDB reachable"

export REPO_ROOT AIDB_URL AIDB_API_KEY_FILE

# ---------------------------------------------------------------------------
# Job 1 — logic pattern indexing
# ---------------------------------------------------------------------------
log "--- Job 1: logic-patterns indexing ---"
LOGIC_STATUS=0
python3 "${REPO_ROOT}/scripts/ai/aq-index-logic-patterns" 2>&1 || LOGIC_STATUS=$?
if [[ "$LOGIC_STATUS" -eq 0 ]]; then
  log "logic-patterns: OK"
else
  warn "logic-patterns: exited ${LOGIC_STATUS} (partial index)"
fi

# ---------------------------------------------------------------------------
# Job 2 — project knowledge corpus
# ---------------------------------------------------------------------------
log "--- Job 2: project knowledge corpus ---"
KNOWLEDGE_STATUS=0
python3 "${REPO_ROOT}/scripts/data/ingest-project-knowledge.py" \
  --paths ai-stack/ dashboard/ scripts/ config/ nix/ docs/ \
  --project nixos-dev-quick-deploy \
  --delay "${INGEST_DELAY}" \
  2>&1 || KNOWLEDGE_STATUS=$?
if [[ "$KNOWLEDGE_STATUS" -eq 0 ]]; then
  log "project-knowledge: OK"
else
  warn "project-knowledge: exited ${KNOWLEDGE_STATUS} (partial ingest)"
fi

# ---------------------------------------------------------------------------
# Write result JSON
# ---------------------------------------------------------------------------
END_TS=$(date +%s)
DURATION=$(( END_TS - START_TS ))
OVERALL=$( [[ "$LOGIC_STATUS" -eq 0 && "$KNOWLEDGE_STATUS" -eq 0 ]] && echo "ok" || echo "partial" )

if [[ -n "$REINDEX_OUTPUT" ]]; then
  mkdir -p "$(dirname "$REINDEX_OUTPUT")" 2>/dev/null || true
  printf '{
  "status": "%s",
  "logic_patterns_exit": %d,
  "project_knowledge_exit": %d,
  "duration_s": %d,
  "timestamp": "%s"
}\n' \
    "$OVERALL" "$LOGIC_STATUS" "$KNOWLEDGE_STATUS" "$DURATION" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    > "$REINDEX_OUTPUT" 2>/dev/null || true
  log "result written to ${REINDEX_OUTPUT}"
fi

log "done — status=${OVERALL} duration=${DURATION}s"
[[ "$OVERALL" == "ok" ]]
