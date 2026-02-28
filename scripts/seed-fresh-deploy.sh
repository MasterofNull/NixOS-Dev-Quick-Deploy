#!/usr/bin/env bash
# scripts/seed-fresh-deploy.sh
#
# One-command bootstrap for a new machine.
# Orchestrates all seeding steps in order after a fresh nixos-rebuild switch.
#
# Steps:
#   1. Wait for AIDB to become healthy (mandatory — exit 1 on timeout)
#   2. Copy ai-stack/agent-memory/MEMORY.md into all ~/.claude/projects/*/memory/ dirs
#   3. Run import-agent-instructions.sh (idempotent upsert)
#   4. If ai-stack/snapshots/query-gaps.jsonl exists: run import-ai-behavior-snapshot.sh
#   5. Run update-mcp-integrity-baseline.sh to seed the integrity hash baseline
#
# Environment:
#   AIDB_URL   Override AIDB base URL (default: http://127.0.0.1:8002)
#   HC_URL     Override hybrid-coordinator base URL (default: http://127.0.0.1:8003)
#
# Usage:
#   bash scripts/seed-fresh-deploy.sh
#   AIDB_URL=http://other-host:8002 bash scripts/seed-fresh-deploy.sh

set -euo pipefail

AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
HC_URL="${HC_URL:-http://127.0.0.1:8003}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HEALTH_TIMEOUT=60

# ---------------------------------------------------------------------------
# Step 1 — Wait for AIDB health
# ---------------------------------------------------------------------------
printf 'step 1: waiting for AIDB health at %s/health (timeout %ds)\n' "$AIDB_URL" "$HEALTH_TIMEOUT"
_elapsed=0
while true; do
    _resp="$(curl -s --max-time 3 "${AIDB_URL}/health" 2>/dev/null || true)"
    if printf '%s' "$_resp" | grep -q '"status".*"ok"'; then
        printf 'step 1: AIDB healthy\n'
        break
    fi
    if [[ $_elapsed -ge $HEALTH_TIMEOUT ]]; then
        printf 'step 1: ERROR — AIDB did not become healthy within %ds\n' "$HEALTH_TIMEOUT" >&2
        exit 1
    fi
    sleep 2
    _elapsed=$((_elapsed + 2))
done

# ---------------------------------------------------------------------------
# Step 2 — Sync MEMORY.md into all ~/.claude/projects/*/memory/ dirs
# ---------------------------------------------------------------------------
printf 'step 2: syncing ai-stack/agent-memory/MEMORY.md to ~/.claude/projects memory dirs\n'
_mem_src="${REPO_ROOT}/ai-stack/agent-memory/MEMORY.md"
if [[ -f "$_mem_src" ]]; then
    _copied=0
    while IFS= read -r -d '' _mem_dir; do
        cp "$_mem_src" "${_mem_dir}/MEMORY.md"
        _copied=$((_copied + 1))
    done < <(find "${HOME}/.claude/projects" -mindepth 2 -maxdepth 2 -type d -name "memory" -print0 2>/dev/null || true)
    if [[ $_copied -eq 0 ]]; then
        printf 'step 2: no ~/.claude/projects/*/memory/ dirs found — skipped\n'
    else
        printf 'step 2: copied to %d memory dir(s)\n' "$_copied"
    fi
else
    printf 'step 2: %s not found — skipped\n' "$_mem_src"
fi

# ---------------------------------------------------------------------------
# Step 3 — Import agent instructions into AIDB (idempotent)
# ---------------------------------------------------------------------------
printf 'step 3: running import-agent-instructions.sh\n'
AIDB_URL="$AIDB_URL" bash "${SCRIPT_DIR}/import-agent-instructions.sh"

# ---------------------------------------------------------------------------
# Step 4 — Import AI behaviour snapshot if present (optional)
# ---------------------------------------------------------------------------
_gaps="${REPO_ROOT}/ai-stack/snapshots/query-gaps.jsonl"
printf 'step 4: checking for query-gaps snapshot at %s\n' "$_gaps"
if [[ -f "$_gaps" ]]; then
    _snapshot_script="${SCRIPT_DIR}/import-ai-behavior-snapshot.sh"
    if [[ -f "$_snapshot_script" ]]; then
        AIDB_URL="$AIDB_URL" bash "$_snapshot_script" || true
    else
        printf 'step 4: import-ai-behavior-snapshot.sh not found — skipped\n'
    fi
else
    printf 'step 4: query-gaps.jsonl not present — skipped\n'
fi

# ---------------------------------------------------------------------------
# Step 5 — Update MCP integrity baseline
# ---------------------------------------------------------------------------
_baseline_script="${SCRIPT_DIR}/update-mcp-integrity-baseline.sh"
printf 'step 5: seeding MCP integrity baseline\n'
if [[ -f "$_baseline_script" ]]; then
    bash "$_baseline_script" || true
else
    printf 'step 5: update-mcp-integrity-baseline.sh not found — skipped\n'
fi

# ---------------------------------------------------------------------------
printf 'seed-fresh-deploy: complete\n'
