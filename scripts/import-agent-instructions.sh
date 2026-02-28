#!/usr/bin/env bash
# scripts/import-agent-instructions.sh
#
# Imports all agent instruction and memory files into AIDB as project=agent-instructions.
# Uses AIDB's upsert semantics (on_conflict_do_update on project+relative_path),
# so this script is fully idempotent — safe to run after every deploy or sync.
#
# Environment:
#   AIDB_URL        Override AIDB base URL (default: http://127.0.0.1:8002)
#   AIDB_API_KEY    API key header value (optional — key enforcement is off by default)
#
# Usage:
#   bash scripts/import-agent-instructions.sh
#   AIDB_URL=http://other-host:8002 bash scripts/import-agent-instructions.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
# Strip whitespace/newlines from key (secret files may have leading blank lines)
AIDB_API_KEY="${AIDB_API_KEY:-$(cat /run/secrets/aidb_api_key 2>/dev/null || true)}"
AIDB_API_KEY="${AIDB_API_KEY//[$'\t\r\n ']/}"
PROJECT="agent-instructions"
PASS=0
FAIL=0

_post() {
    local rel_path="$1" title="$2" file="$3" content_type="${4:-text/markdown}"
    if [ ! -f "$file" ]; then
        echo "SKIP  $title  (not found: $file)"
        return 0
    fi

    local payload
    payload=$(jq -n \
        --arg project  "$PROJECT" \
        --arg path     "$rel_path" \
        --arg title    "$title" \
        --arg ctype    "$content_type" \
        --rawfile content "$file" \
        '{
            project:           $project,
            relative_path:     $path,
            title:             $title,
            content:           $content,
            content_type:      $ctype,
            source_trust_level: "trusted",
            status:            "approved"
        }')

    local args=(-s -o /dev/null -w "%{http_code}"
                -X POST "${AIDB_URL}/documents"
                -H "Content-Type: application/json"
                -d "$payload")
    [ -n "${AIDB_API_KEY:-}" ] && args+=(-H "X-API-Key: $AIDB_API_KEY")

    local code
    code=$(curl "${args[@]}")

    if [ "$code" = "200" ] || [ "$code" = "201" ]; then
        echo "OK    $title"
        (( PASS++ )) || true
    else
        echo "FAIL  $title  (HTTP $code)"
        (( FAIL++ )) || true
    fi
}

printf 'import-agent-instructions: target=%s project=%s\n\n' "${AIDB_URL}" "${PROJECT}"

# --- Agent instruction files (source of truth = git repo) ---
_post "CLAUDE.md"                     "Project Rules (CLAUDE.md)"           "${REPO_ROOT}/CLAUDE.md"
_post "AGENTS.md"                     "Agent Instructions (AGENTS.md)"      "${REPO_ROOT}/AGENTS.md"
_post ".aider.md"                     "Aider Conventions (.aider.md)"       "${REPO_ROOT}/.aider.md"
_post ".gemini/context.md"            "Gemini CLI Context"                   "${REPO_ROOT}/.gemini/context.md"
_post "ai-stack/prompts/registry.yaml" "Prompt Registry"                    "${REPO_ROOT}/ai-stack/prompts/registry.yaml" "text/yaml"

# --- Agent memory (repo copy is authoritative for AIDB; live copy synced by sync-agent-instructions) ---
_post "ai-stack/agent-memory/MEMORY.md" "Agent Memory (MEMORY.md)"          "${REPO_ROOT}/ai-stack/agent-memory/MEMORY.md"

# --- QA plan (tracks all phases, tasks, and success criteria) ---
_post "AI-STACK-QA-PLAN.md"            "QA Plan (AI-STACK-QA-PLAN.md)"      "${REPO_ROOT}/AI-STACK-QA-PLAN.md"

# --- Custom tooling scripts (indexed for RAG retrieval during QA/dev sessions) ---
PROJECT="dev-tools"
_post "scripts/aq-qa"                   "QA Phase Runner (aq-qa)"             "${REPO_ROOT}/scripts/aq-qa"            "text/x-shellscript"
_post "scripts/aq-hints"                "Workflow Hints CLI (aq-hints)"        "${REPO_ROOT}/scripts/aq-hints"         "text/x-shellscript"
_post "scripts/aq-report"              "AI Stack Report (aq-report)"          "${REPO_ROOT}/scripts/aq-report"        "text/x-shellscript"
_post "scripts/aq-prompt-eval"         "Prompt Eval CLI (aq-prompt-eval)"     "${REPO_ROOT}/scripts/aq-prompt-eval"   "text/x-shellscript"
_post "scripts/aq-gaps"                "Gap Detection CLI (aq-gaps)"          "${REPO_ROOT}/scripts/aq-gaps"          "text/x-shellscript"
_post "scripts/check-mcp-health.sh"   "MCP Health Checker"                   "${REPO_ROOT}/scripts/check-mcp-health.sh"  "text/x-shellscript"
_post "scripts/ai-stack-health.sh"    "AI Stack Health (ai-stack-health.sh)" "${REPO_ROOT}/scripts/ai-stack-health.sh"   "text/x-shellscript"
_post "scripts/check-mcp-integrity.sh" "MCP Integrity Checker"               "${REPO_ROOT}/scripts/check-mcp-integrity.sh" "text/x-shellscript"
_post "scripts/sync-agent-instructions" "Agent Instruction Sync"             "${REPO_ROOT}/scripts/sync-agent-instructions" "text/x-python"
_post "config/service-endpoints.sh"   "Service Endpoints Config"             "${REPO_ROOT}/config/service-endpoints.sh"  "text/x-shellscript"

printf '\nimport-agent-instructions: %d imported, %d failed\n' "${PASS}" "${FAIL}"
[ "$FAIL" -eq 0 ] || exit 1
