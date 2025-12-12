#!/usr/bin/env bash
#
# Smoke-test a few real-world workflows referenced in AGENTS.md.
# The script keeps everything deterministic by falling back to warnings when
# optional services (Lemonade/AIDB) are offline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KNOWLEDGE_SKILL="$REPO_ROOT/.agent/skills/aidb-knowledge/SKILL.md"
RAG_SKILL="$REPO_ROOT/.agent/skills/rag-techniques/SKILL.md"
PROJECT_IMPORT_SKILL="$REPO_ROOT/.agent/skills/project-import/SKILL.md"
SMART_CONFIG_GEN="$REPO_ROOT/scripts/smart_config_gen.sh"

AIDB_BASE_URL="${AIDB_BASE_URL:-http://localhost:8091}"

tmp_config=""

cleanup() {
    [[ -n "$tmp_config" && -f "$tmp_config" ]] && rm -f "$tmp_config"
}
trap cleanup EXIT

echo "🔎 Checking knowledge skill"
python "$KNOWLEDGE_SKILL" --search "deployment" --limit 3 || true

echo "📋 Listing RAG playbooks"
python "$RAG_SKILL" --list || true

echo "📥 Dry-run documentation sync"
python "$PROJECT_IMPORT_SKILL" --dry-run || true

echo "🧠 Attempting configuration generation"
tmp_config="$(mktemp /tmp/aidb-config-XXXX.nix)"
if curl -fs --max-time 3 "${AIDB_BASE_URL%/}/health" >/dev/null 2>&1; then
    if "$SMART_CONFIG_GEN" --description "Enable git + home-manager" --output "$tmp_config" >/dev/null 2>&1; then
        echo "✅ Generated config stored at $tmp_config"
    else
        echo "⚠️  smart_config_gen.sh failed. Check AIDB logs." >&2
    fi
else
    echo "⚠️  AIDB MCP not reachable (${AIDB_BASE_URL%/}/health). Skipping config generation."
fi

echo "🎯 Workflow smoke test complete."
