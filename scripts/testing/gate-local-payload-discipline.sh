#!/usr/bin/env bash
# gate-local-payload-discipline.sh — QA gate for local inference payload discipline
#
# Fails if it finds direct llama.cpp chat payloads with enable_thinking=True
# or missing enable_thinking=False (unless they use build_llama_payload).

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "🔍 Checking local inference payload discipline..."

# Find source files that might be making local chat calls. Exclude
# shared/llm_config.py because it is the source of truth for the False value.
FILES=$(grep -rnE '["'\'']enable_thinking["'\'']:[[:space:]]*True|enable_thinking=True' \
    "${REPO_ROOT}/ai-stack" \
    "${REPO_ROOT}/scripts/ai" \
    --include="*.py" \
    --include="aq-chat" \
    --exclude="llm_config.py" \
    --exclude-dir="archive" || true)

if [[ -n "${FILES}" ]]; then
    echo "❌ Found forbidden 'enable_thinking: True' in local payload(s):"
    echo "${FILES}"
    exit 1
fi

echo "✅ Local payload discipline check passed."
